"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, isLoggedIn, getToken } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string; role: string } | null>(null);

  // Protect route & fetch user data
  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/auth/me", {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        });

        if (!res.ok) throw new Error("Failed to fetch user");
        const data = await res.json();
        setUser({ email: data.email, role: data.role });
      } catch (err) {
        console.error(err);
      }
    };

    fetchUser();
  }, [router]);

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <div className="p-6">
      <Card className="p-6 space-y-4 max-w-md">
        <h2 className="text-2xl font-bold">User Profile</h2>
        {user ? (
          <div className="space-y-2">
            <p>
              <strong>Email:</strong> {user.email}
            </p>
            <p>
              <strong>Role:</strong> {user.role}
            </p>
          </div>
        ) : (
          <p>Loading user info...</p>
        )}
        <div className="flex gap-2">
          <Button onClick={handleLogout} variant="destructive">
            Logout
          </Button>
        </div>
      </Card>
    </div>
  );
}
