"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useState } from "react";

type Message = { sender: "user" | "bot"; text?: string; structured?: any };

export default function AnalyzePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input; // capture current input
    setInput(""); // clear input immediately

    // Add user message
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);

    // Add "analyzing..." placeholder
    const placeholderIndex = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { sender: "bot", text: "Analyzing your message..." },
    ]);

    try {
      setLoading(true);
      const res = await fetch("http://127.0.0.1:8000/analyze/", {
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

      // Clean and parse AI result
      let aiResult = data.ai_result || "";
      if (typeof aiResult === "string") {
        aiResult = aiResult.replace(/```json/gi, "").replace(/```/g, "").trim();
      }

      let parsed: any = null;
      try {
        parsed = typeof aiResult === "string" ? JSON.parse(aiResult) : aiResult;
      } catch {
        parsed = null;
      }

      // Replace placeholder with actual result
      setMessages((prev) =>
        prev.map((msg, idx) =>
          idx === placeholderIndex
            ? parsed
              ? { sender: "bot", structured: parsed }
              : { sender: "bot", text: aiResult }
            : msg
        )
      );
    } catch (err) {
      console.error("Error fetching analysis:", err);

      // Replace placeholder with error
      setMessages((prev) =>
        prev.map((msg, idx) =>
          idx === placeholderIndex
            ? { sender: "bot", text: "Failed to fetch analysis." }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${
              msg.sender === "user" ? "justify-end" : "justify-start"
            }`}
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
                    <strong>Explanation:</strong>{" "}
                    {msg.structured.explanation}
                  </p>
                  {msg.structured.tips && (
                    <ul className="mt-2 list-disc pl-5">
                      {msg.structured.tips.map((tip: string, i: number) => (
                        <li key={i}>{tip}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                msg.text
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
