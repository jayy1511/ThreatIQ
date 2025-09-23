"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";

interface AnalysisRecord {
  id: number;
  text: string;
  sender: string;
  result: any;
  created_at: string;
}

export default function HistoryPage() {
  const router = useRouter();
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [error, setError] = useState("");

  // ✅ Protect route
  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
    }
  }, [router]);

  // ✅ Fetch history
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/analyze/history", {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
          },
        });

        if (!res.ok) throw new Error("Failed to fetch history");

        const data = await res.json();

        // ✅ Reverse order so newest first
        setRecords(data.reverse());
      } catch (err: any) {
        setError(err.message || "Something went wrong");
      }
    };

    if (isLoggedIn()) {
      fetchHistory();
    }
  }, []);

  return (
    <div className="flex flex-col p-6 h-screen overflow-y-auto">
      <h2 className="text-2xl font-bold mb-4">History</h2>

      {error && (
        <div className="flex items-center gap-2 text-red-500 text-sm mb-4">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {records.length === 0 && !error && (
        <p className="text-muted-foreground">No past analyses found.</p>
      )}

      <div className="grid gap-4">
        {records.map((rec) => {
          let ai = rec.result?.ai_result;
          if (typeof ai === "string") {
            try {
              ai = JSON.parse(
                ai.replace(/```json/g, "").replace(/```/g, "")
              );
            } catch {
              ai = null;
            }
          }

          return (
            <Card key={rec.id} className="p-4 space-y-2">
              {/* ✅ Local time */}
              <p className="text-sm text-muted-foreground">
                {new Date(rec.created_at).toLocaleString(undefined, {
                  dateStyle: "short",
                  timeStyle: "medium",
                })}
              </p>

              <p className="font-medium">Input: {rec.text}</p>

              {ai ? (
                <div className="space-y-2">
                  <p>
                    <span className="font-bold">Judgment:</span>{" "}
                    <span
                      className={
                        ai.judgment === "Phishing"
                          ? "text-red-500"
                          : "text-green-500"
                      }
                    >
                      {ai.judgment}
                    </span>
                  </p>
                  <p>
                    <span className="font-bold">Explanation:</span>{" "}
                    {ai.explanation}
                  </p>
                  {ai.tips && (
                    <div>
                      <p className="font-bold">Tips:</p>
                      <ul className="list-disc pl-6 text-sm">
                        {ai.tips.map((tip: string, idx: number) => (
                          <li key={idx}>{tip}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">
                  No AI analysis available.
                </p>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
