"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn, getToken } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface AnalysisRecord {
  text: string;
  sender: string;
  result: any;
  created_at: string;
}

export default function HistoryPage() {
  const router = useRouter();
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [error, setError] = useState("");

  // Protect route
  useEffect(() => {
    if (!isLoggedIn()) router.push("/login");
  }, [router]);

  // Fetch history
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/analyze/history`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) throw new Error("Failed to fetch history");

        const data = await res.json();
        setRecords(data.reverse());
      } catch (err: any) {
        setError(err.message);
      }
    };

    if (isLoggedIn()) fetchHistory();
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
        {records.map((rec, index) => {
          const ai = rec.result; // <<<<<<<<< FIXED (direct from backend)

          return (
            <Card key={index} className="p-4 space-y-3">
              {/* Timestamp */}
              <p className="text-sm text-muted-foreground">
                {new Date(rec.created_at).toLocaleString()}
              </p>

              {/* Input message */}
              <p className="font-medium">Input: {rec.text}</p>

              {/* AI Analysis */}
              {ai ? (
                <div className="space-y-2">
                  <p>
                    <strong>Judgment:</strong>{" "}
                    <span
                      className={
                        ai.judgment === "Phishing"
                          ? "text-red-500"
                          : ai.judgment === "Safe"
                          ? "text-green-500"
                          : "text-yellow-500"
                      }
                    >
                      {ai.judgment}
                    </span>
                  </p>

                  <p>
                    <strong>Explanation:</strong> {ai.explanation}
                  </p>

                  {ai.tips && (
                    <>
                      <p className="font-bold">Tips:</p>
                      <ul className="list-disc pl-6 text-sm">
                        {ai.tips.map((tip: string, idx: number) => (
                          <li key={idx}>{tip}</li>
                        ))}
                      </ul>
                    </>
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
