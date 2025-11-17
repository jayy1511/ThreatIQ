"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/auth";

type Role = "user" | "assistant";

type ChatTurn = {
  role: Role;
  content: string;
};

export default function SecurityChatPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [chat, setChat] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // avoid hydration issues + redirect if not logged in
  useEffect(() => {
    setMounted(true);
    const token = getToken();
    if (!token) {
      router.push("/login");
    }
  }, [router]);

  if (!mounted) return null;

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    setInput("");
    setError(null);

    // optimistic user message
    const newHistory: ChatTurn[] = [...chat, { role: "user", content: text }];
    setChat(newHistory);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/security-chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          history: newHistory.map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Chat request failed");
      }

      const reply = (data?.reply as string) ?? "";
      setChat([...newHistory, { role: "assistant", content: reply }]);
    } catch (err: any) {
      console.error("security-chat error", err);
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!loading) {
        sendMessage();
      }
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <main className="flex-1 flex flex-col items-center px-4 py-8">
        <div className="w-full max-w-3xl space-y-4">
          <h1 className="text-2xl font-semibold">Security Chat</h1>
          <p className="text-sm text-muted-foreground">
            Ask ThreatIQ anything about online safety, phishing, passwords,
            or paste a message / email to check if it looks suspicious. You can
            continue the conversation like a normal chat.
          </p>

          {/* Chat history */}
          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {chat.map((turn, idx) => (
              <div
                key={idx}
                className={`flex ${
                  turn.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <Card
                  className={
                    "p-3 max-w-[80%] whitespace-pre-wrap " +
                    (turn.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-card text-card-foreground")
                  }
                >
                  {turn.content}
                </Card>
              </div>
            ))}
          </div>

          {/* Error */}
          {error && <p className="text-sm text-red-500">{error}</p>}

          {/* Input */}
          <div className="p-4 border border-border rounded-md flex gap-2 bg-background">
            <Input
              placeholder="Ask a security question or paste a message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <Button onClick={sendMessage} disabled={loading || !input.trim()}>
              {loading ? "Thinking..." : "Send"}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
