"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";
import { getUserEmail, clearUser, clearToken } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function Sidebar() {
  const router = useRouter();
  const email = getUserEmail();
  const initial = email ? email[0].toUpperCase() : "U";

  const handleLogout = () => {
    clearToken();
    clearUser();
    router.push("/login");
  };

  return (
    <aside className="w-56 bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col justify-between p-4">
      {/* Top section */}
      <div>
        <h1 className="font-bold text-lg mb-6">ThreatIQ</h1>
        <nav className="space-y-2">
          <Button variant="ghost" asChild className="w-full justify-start">
            <Link href="/dashboard">Dashboard</Link>
          </Button>
          <Button variant="ghost" asChild className="w-full justify-start">
            <Link href="/analyze">Analyze</Link>
          </Button>
          <Button variant="ghost" asChild className="w-full justify-start">
            <Link href="/history">History</Link>
          </Button>
          <Button variant="ghost" asChild className="w-full justify-start">
            <Link href="/settings">Settings</Link>
          </Button>
        </nav>
      </div>

      {/* Bottom section */}
      <div className="flex items-center justify-between mt-6 gap-2">
        {/* Avatar with initial */}
        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-bold">
          {initial}
        </div>
        <ModeToggle />
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </aside>
  );
}
