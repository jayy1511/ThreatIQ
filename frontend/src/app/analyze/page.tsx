"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useState } from "react";

type Message = { sender: "user" | "bot"; text?: string; structured?: any };

export default function AnalyzePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  const handleSend = async () => {
    if (!input.trim()) return;

    // Add user message
    setMessages((prev) => [...prev, { sender: "user", text: input }]);

    try {
      const res = await fetch("http://127.0.0.1:8000/analyze/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
        },
        body: JSON.stringify({ text: input, sender: "" }),
      });

      if (!res.ok) throw new Error("Analysis failed");

      const data = await res.json();

      // 🟢 Clean and parse AI result
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

      setMessages((prev) => [
        ...prev,
        parsed
          ? { sender: "bot", structured: parsed }
          : { sender: "bot", text: aiResult },
      ]);
    } catch (err) {
      console.error("Error fetching analysis:", err);
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "⚠️ Failed to fetch analysis." },
      ]);
    }

    setInput("");
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
        />
        <Button onClick={handleSend}>Send</Button>
      </div>
    </div>
  );
}
