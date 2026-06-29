// API Client with cold-start handling for Render Free tier
import { auth } from './firebase';
import { API_BASE_URL } from './config';

// ============================================
// Types
// ============================================

// Must stay aligned with backend schemas
export type UserGuess = 'phishing' | 'safe' | 'unclear';
export const MAX_MESSAGE_LENGTH = 12_000;

export interface AnalysisRequest {
    message: string;
    user_guess?: UserGuess;
    user_id?: string;
}

export interface ClassificationResult {
    label: 'phishing' | 'suspicious' | 'safe';
    confidence: number;
    reason_tags: string[];
    explanation: string;
}

export interface PhishingExample {
    message: string;
    category: string;
    similarity?: number;
    description?: string;
}

export interface QuizQuestion {
    question: string;
    options: string[];
    correct_answer: string;
}

export interface CoachResponse {
    verdict: string;
    explanation: string;
    similar_examples: PhishingExample[];
    tips: string[];
    quiz?: QuizQuestion;
}

export interface AnalysisResponse {
    classification: ClassificationResult;
    coach_response: CoachResponse;
    session_id: string;
    category?: string;
    was_correct?: boolean;
}

export interface ServiceHealthStatus {
    status: 'ready' | 'warming_up' | 'unavailable' | 'error';
    message?: string;
    retry_after_seconds?: number;
}

export interface TodayLesson {
    lesson: {
        lesson_id: string;
        title: string;
        topic: string;
        content: string;
        quiz: Array<{
            question: string;
            options: string[];
            correct_index: number;
        }>;
    };
    date: string;
    already_completed: boolean;
}

export interface LessonProgress {
    xp_total: number;
    level: number;
    streak_current: number;
    streak_best: number;
    last_lesson_completed_date: string | null;
    lessons_completed: number;
    last_7_days: Array<{ date: string; completed: boolean }>;
}

export interface ProfileSummary {
    total_analyzed: number;
    correct: number;
    incorrect: number;
    accuracy: number;
    weak_spots: string[];
    recent_categories: string[];
}

export interface LessonCompleteRequest {
    lesson_id: string;
    answers: number[];
}

export interface LessonCompleteResponse {
    score_percent: number;
    xp_earned: number;
    xp_total: number;
    level: number;
    streak_current: number;
    streak_best: number;
    last_completed_date: string;
    already_completed_today: boolean;
    message: string;
    correct_answers: number[];
}

// ============================================
// API Error
// ============================================

export class ApiError extends Error {
    status: number;
    isWarmingUp: boolean;

    constructor(message: string, status: number, isWarmingUp = false) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.isWarmingUp = isWarmingUp;
    }
}

// ============================================
// Auth Token
// ============================================

async function getAuthToken(): Promise<string | null> {
    const user = auth.currentUser;
    if (!user) return null;

    try {
        return await user.getIdToken();
    } catch (error) {
        console.error('Failed to get auth token:', error);
        return null;
    }
}

// ============================================
// Fetch Wrapper with Cold-Start Handling
// ============================================

async function apiFetch<T>(
    endpoint: string,
    options: {
        method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
        body?: any;
        authenticated?: boolean;
        timeout?: number;
        retryOnWarmup?: boolean;
    } = {}
): Promise<T> {
    const {
        method = 'GET',
        body,
        authenticated = false,
        timeout = 60000,
        retryOnWarmup = true
    } = options;

    if (!API_BASE_URL) {
        throw new ApiError('API base URL not configured', 0);
    }

    const url = `${API_BASE_URL}/api${endpoint}`;
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };

    if (authenticated) {
        const token = await getAuthToken();
        if (!token) {
            throw new ApiError('Not authenticated', 401);
        }
        headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Handle warming up errors
        if (response.status === 502 || response.status === 503 || response.status === 504) {
            let errorMessage = 'Analysis service warming up, please retry in 30 seconds';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorMessage;
            } catch { }
            throw new ApiError(errorMessage, response.status, true);
        }

        if (!response.ok) {
            let errorMessage = `Request failed: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorMessage;
            } catch { }
            throw new ApiError(errorMessage, response.status);
        }

        return await response.json();
    } catch (error: any) {
        clearTimeout(timeoutId);

        if (error.name === 'AbortError') {
            throw new ApiError('Request timeout - service may be warming up', 408, true);
        }

        if (error instanceof ApiError) {
            throw error;
        }

        throw new ApiError(
            error.message || 'Network error. Please check your connection.',
            0
        );
    }
}

// ============================================
// HEALTH CHECK (for cold-start detection)
// ============================================

export async function checkServiceHealth(): Promise<ServiceHealthStatus> {
    try {
        return await apiFetch<ServiceHealthStatus>('/analysis-service/health', {
            timeout: 15000,
            retryOnWarmup: false,
        });
    } catch (error) {
        return {
            status: 'unavailable',
            message: error instanceof Error ? error.message : 'Health check failed',
            retry_after_seconds: 30,
        };
    }
}

// ============================================
// PUBLIC ENDPOINTS
// ============================================

export async function analyzePublic(message: string, userGuess?: string): Promise<AnalysisResponse> {
    return apiFetch<AnalysisResponse>('/analyze-public', {
        method: 'POST',
        body: { message, user_guess: userGuess },
        timeout: 120000, // 2 min for cold starts
    });
}

// ============================================
// AUTHENTICATED ENDPOINTS
// ============================================

export async function analyze(
    message: string,
    userId: string,
    userGuess?: string
): Promise<AnalysisResponse> {
    // Generate a simple UUID for idempotency
    const requestId = crypto.randomUUID 
        ? crypto.randomUUID() 
        : Date.now().toString(36) + Math.random().toString(36).substring(2);

    return apiFetch<AnalysisResponse>('/analyze', {
        method: 'POST',
        body: { message, user_id: userId, user_guess: userGuess, request_id: requestId },
        authenticated: true,
        timeout: 120000,
    });
}

export async function getTodayLesson(): Promise<TodayLesson> {
    return apiFetch<TodayLesson>('/lessons/today', { authenticated: true });
}

export async function completeLesson(
    lessonId: string,
    answers: number[]
): Promise<LessonCompleteResponse> {
    return apiFetch<LessonCompleteResponse>('/lessons/complete', {
        method: 'POST',
        body: { lesson_id: lessonId, answers },
        authenticated: true,
    });
}

export async function getLessonProgress(): Promise<LessonProgress> {
    return apiFetch<LessonProgress>('/lessons/progress', { authenticated: true });
}

export async function getProfileSummary(userId: string): Promise<ProfileSummary> {
    return apiFetch<ProfileSummary>(`/profile/${userId}/summary`, { authenticated: true });
}

export async function getAnalysisHistory(userId: string): Promise<{ history: any[] }> {
    return apiFetch<{ history: any[] }>(`/profile/${userId}/history`, { authenticated: true });
}

export async function getGmailStatus(): Promise<any> {
    try {
        return await apiFetch<any>('/gmail/status', { authenticated: true });
    } catch {
        return { connected: false, error: 'Gmail integration not available' };
    }
}
