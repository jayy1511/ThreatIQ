"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { API_BASE } from "@/lib/api";

type StructuredResult = {
  judgment: string;
  explanation: string;
  tips?: string[];
};

type Message = {
  sender: "user" | "bot";
  text?: string;
  structured?: StructuredResult;
};

export default function AnalyzePage() {
  const [mounted, setMounted] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setInput(""); // clear immediately

    // add user message
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);

    // add placeholder
    const placeholderIndex = messages.length + 1;
    setMessages((prev) => [...prev, { sender: "bot", text: "Analyzing your message..." }]);

    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/analyze/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
        },
        body: JSON.stringify({ text: userText, sender: "" }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Analysis failed");
      }

      // Clean & parse AI result
      let aiResult: unknown = (data as any).ai_result ?? "";
      if (typeof aiResult === "string") {
        aiResult = aiResult.replace(/```json/gi, "").replace(/```/g, "").trim();
      }

      let parsed: StructuredResult | null = null;
      if (typeof aiResult === "string") {
        try {
          parsed = JSON.parse(aiResult);
        } catch {
          parsed = null;
        }
      } else if (aiResult && typeof aiResult === "object") {
        parsed = aiResult as StructuredResult;
      }

      // replace placeholder
      setMessages((prev) =>
        prev.map((msg, idx) =>
          idx === placeholderIndex
            ? parsed
              ? { sender: "bot", structured: parsed }
              : { sender: "bot", text: typeof aiResult === "string" ? aiResult : "Could not parse AI response." }
            : msg
        )
      );
    } catch (err) {
      console.error("Error fetching analysis:", err);
      setMessages((prev) =>
        prev.map((msg, idx) =>
          idx === placeholderIndex ? { sender: "bot", text: "Failed to fetch analysis." } : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  // Avoid SSR output to prevent hydration mismatch
  if (!mounted) return null;

  return (
    <div className="flex flex-col h-screen">
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            <Card
              className={`p-3 max-w-xl whitespace-pre-wrap ${
                msg.sender === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-card-foreground"
              }`}
            >
              {msg.structured ? (
                <div>
                  <p>
                    <strong>Judgment:</strong> {msg.structured.judgment}
                  </p>
                  <p className="mt-2">
                    <strong>Explanation:</strong> {msg.structured.explanation}
                  </p>
                  {Array.isArray(msg.structured.tips) && msg.structured.tips.length > 0 && (
                    <ul className="mt-2 list-disc pl-5">
                      {msg.structured.tips.map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                msg.text || ""
              )}
            </Card>
          </div>
        ))}
      </div>

      {/* Input box */}
      <div className="p-4 border-t border-border flex gap-2">
        <Input
          placeholder="Paste an email or message to analyze..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          disabled={loading}
        />
        <Button onClick={handleSend} disabled={loading}>
          {loading ? "Analyzing..." : "Send"}
        </Button>
      </div>
    </div>
  );
}
