"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, clearToken } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { jwtDecode } from "jwt-decode";

interface FirebaseToken {
  email?: string;
  user_id?: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<{ email: string; uid: string } | null>(
    null
  );

  useEffect(() => {
    const token = getToken();

    if (!token) {
      router.push("/login");
      return;
    }

    try {
      const decoded: FirebaseToken = jwtDecode(token);
      setProfile({
        email: decoded.email || "Unknown",
        uid: decoded.user_id || "N/A",
      });
    } catch (e) {
      console.error(e);
      router.push("/login");
    }
  }, [router]);

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <div className="p-6">
      <Card className="p-6 space-y-4 max-w-md">
        <h2 className="text-2xl font-bold">User Profile</h2>

        {!profile ? (
          <p>Loading...</p>
        ) : (
          <div className="space-y-2">
            <p>
              <strong>Email:</strong> {profile.email}
            </p>
            <p>
              <strong>UID:</strong> {profile.uid}
            </p>
          </div>
        )}

        <Button onClick={handleLogout} variant="destructive">
          Logout
        </Button>
      </Card>
    </div>
  );
}
