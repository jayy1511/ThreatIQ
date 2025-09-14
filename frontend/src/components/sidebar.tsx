"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/analyze", label: "Analyze" },
    { href: "/history", label: "History" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <aside className="w-56 bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col justify-between p-4">
      <div>
        <h1 className="font-bold text-lg mb-6">ThreatIQ</h1>
        <nav className="space-y-2">
          {links.map((link) => (
            <Link key={link.href} href={link.href}>
              <Button
                variant={pathname === link.href ? "default" : "ghost"}
                className="w-full justify-start"
              >
                {link.label}
              </Button>
            </Link>
          ))}
        </nav>
      </div>

      <div className="flex items-center justify-between mt-6">
        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-bold">
          N
        </div>
        <ModeToggle />
      </div>
    </aside>
  );
}
