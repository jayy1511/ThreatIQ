"use client";

import { useRouter } from "next/navigation";
import { clearToken, getToken } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const router = useRouter();

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <div className="p-6">
      <Card className="p-6 space-y-4 max-w-md">
        <h2 className="text-2xl font-bold">User Profile</h2>
        <p>Email: (fetched later using /me endpoint if available)</p>
        <div className="flex gap-2">
          <Button onClick={handleLogout} variant="destructive">
            Logout
          </Button>
        </div>
      </Card>
    </div>
  );
}
