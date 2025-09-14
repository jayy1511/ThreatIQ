"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";

export default function HistoryPage() {
  const router = useRouter();

  // ✅ Protect route
  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
    }
  }, [router]);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">History</h2>
      <p>Your past analyses will appear here.</p>
    </div>
  );
}
