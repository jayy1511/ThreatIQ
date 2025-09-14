"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
    }
  }, [router]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="mt-2 text-muted-foreground">
        Welcome to your ThreatIQ dashboard.
      </p>
    </div>
  );
}
