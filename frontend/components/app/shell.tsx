"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BookOpen,
  Bot,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Siren,
  Upload,
} from "lucide-react";

import { api, DEMO_MODE, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/uploads", label: "Log Uploads", icon: Upload },
  { href: "/analyses", label: "Analyses", icon: Activity },
  { href: "/incidents", label: "Incidents", icon: Siren },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<User>("/api/v1/auth/me")
      .then((u) => {
        setUser(u);
        setReady(true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        <Bot className="mr-2 h-5 w-5 animate-pulse" /> Loading OpsPilot…
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-card">
        <div className="flex items-center gap-2 border-b px-4 py-4">
          <Bot className="h-6 w-6 text-primary" />
          <div>
            <div className="text-sm font-semibold leading-tight">OpsPilot AI</div>
            <div className="text-xs text-muted-foreground">Infrastructure copilot</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t p-3">
          <div className="mb-2 truncate text-xs text-muted-foreground">{user?.email}</div>
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => {
              setToken(null);
              router.replace("/login");
            }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {DEMO_MODE && (
          <div className="flex items-center justify-center gap-2 border-b bg-primary/10 px-4 py-1.5 text-xs text-foreground">
            <Badge variant="info">Demo</Badge>
            <span className="text-muted-foreground">
              Sandboxed session with sample data — everything resets when your session ends.
            </span>
          </div>
        )}
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
