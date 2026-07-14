import axios from "axios";
import { auth } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add a request interceptor to include the Firebase token
api.interceptors.request.use(async (config) => {
  try {
    const user = auth.currentUser;
    if (user) {
      const token = await user.getIdToken();
      // Use the set method to properly set headers in Axios
      config.headers.set("Authorization", `Bearer ${token}`);
    }
  } catch (error) {
    console.error("Error attaching token:", error);
  }
  return config;
});

// Helper to generate UUID v4
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Must stay aligned with backend schemas
export type UserGuess = 'phishing' | 'safe' | 'unclear';
export const MAX_MESSAGE_LENGTH = 12_000;

export const analyzeMessage = async (
  message: string,
  userGuess: UserGuess,
  userId: string
) => {
  const requestId = generateUUID();
  const response = await api.post("/api/analyze", {
    message,
    user_guess: userGuess,
    user_id: userId,
    request_id: requestId,
  });
  return response.data;
};

export const analyzePublicMessage = async (
  message: string,
  userGuess: UserGuess
) => {
  const response = await api.post("/api/analyze-public", {
    message,
    user_guess: userGuess,
  });
  return response.data;
};

// ── Streaming analysis (C1) ───────────────────────────────────────────────────

export type StreamStage =
  | "started"
  | "classification_started"
  | "classification_complete"
  | "evidence_started"
  | "evidence_complete"
  | "coach_started"
  | "coach_complete"
  | "complete"
  | "error";

export interface StreamEvent {
  stage: StreamStage;
  message: string;
  data?: Record<string, unknown>;
  result?: unknown;
}

/**
 * Stream a staged analysis via Server-Sent Events.
 *
 * Calls onEvent for every SSE event received from the backend.
 * The final event has stage="complete" and contains the full result.
 * If streaming fails (network error, service down) it calls onEvent
 * with stage="error" so the caller can fall back gracefully.
 *
 * Returns a cleanup function that aborts the stream if called.
 */
export function streamAnalyzeMessage(
  message: string,
  userGuess: UserGuess,
  userId: string,
  onEvent: (event: StreamEvent) => void
): { abort: () => void } {
  const controller = new AbortController();
  const requestId = generateUUID();

  (async () => {
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const resp = await fetch(`${API_URL}/api/analyze/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message,
          user_guess: userGuess,
          user_id: userId,
          request_id: requestId,
        }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        onEvent({ stage: "error", message: "Analysis service unavailable" });
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE lines are separated by \n\n
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          for (const line of part.split("\n")) {
            if (line.startsWith("data: ")) {
              try {
                const event: StreamEvent = JSON.parse(line.slice(6));
                onEvent(event);
              } catch {
                // malformed line — skip
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as { name?: string }).name === "AbortError") return;
      console.error("Stream error:", err);
      onEvent({ stage: "error", message: "Analysis failed" });
    }
  })();

  return { abort: () => controller.abort() };
}

// Single aggregate endpoint — replaces 4 separate dashboard calls
export const getDashboard = async () => {
  const response = await api.get(`/api/dashboard`);
  return response.data as {
    summary: {
      total_analyzed: number;
      accuracy: number;
      categories_seen: number;
      weak_spots: string[];
    } | null;
    lesson_progress: {
      xp_total: number;
      level: number;
      streak_current: number;
      streak_best: number;
      last_lesson_completed_date: string | null;
      lessons_completed: number;
    } | null;
    today_lesson: {
      lesson: { lesson_id: string; title: string; topic: string };
      date: string;
      already_completed: boolean;
      completion_score: number | null;
    } | null;
    gmail: { connected: boolean; email: string | null };
  };
};

export const getUserProfile = async (userId: string) => {
  const response = await api.get(`/api/profile/${userId}`);
  return response.data.profile;
};

export const getUserSummary = async (userId: string) => {
  const response = await api.get(`/api/profile/${userId}/summary`);
  return response.data;
};

export const getUserHistory = async (userId: string) => {
  const response = await api.get(`/api/profile/${userId}/history`);
  return response.data.history;
};

export const deleteHistoryItem = async (userId: string, itemId: string) => {
  const response = await api.delete(`/api/profile/${userId}/history/${itemId}`);
  return response.data;
};

export const clearHistory = async (userId: string) => {
  const response = await api.delete(`/api/profile/${userId}/history`);
  return response.data;
};

export const updatePrivacySettings = async (
  userId: string,
  saveMessageText: boolean
) => {
  const response = await api.patch(`/api/profile/${userId}/settings`, {
    save_message_text: saveMessageText,
  });
  return response.data;
};

export const getGmailStatus = async () => {
  const response = await api.get("/api/gmail/status");
  return response.data;
};

export const getGmailConnectUrl = async () => {
  const response = await api.get("/api/gmail/connect");
  return response.data;
};

export const disconnectGmail = async () => {
  const response = await api.post("/api/gmail/disconnect");
  return response.data;
};

export const runGmailTriage = async (params: {
  limit?: number;
  mark_spam?: boolean;
  archive_safe?: boolean;
}) => {
  const response = await api.post("/api/gmail/triage", params);
  return response.data;
};

export const getGmailHistory = async (limit: number = 50) => {
  const response = await api.get(`/api/gmail/history?limit=${limit}`);
  return response.data;
};

// ============== LESSON APIs ==============

export const getTodayLesson = async () => {
  const response = await api.get("/api/lessons/today");
  return response.data;
};

export const completeLesson = async (lessonId: string, answers: number[]) => {
  const response = await api.post("/api/lessons/complete", {
    lesson_id: lessonId,
    answers,
  });
  return response.data;
};

export const getLessonProgress = async () => {
  const response = await api.get("/api/lessons/progress");
  return response.data;
};

export const getRecentLessons = async (limit: number = 5) => {
  const response = await api.get(`/api/lessons/recent?limit=${limit}`);
  return response.data;
};

export const getLessonsList = async () => {
  const response = await api.get("/api/lessons/list");
  return response.data;
};

export default api;
