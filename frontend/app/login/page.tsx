"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Play, ShieldCheck } from "lucide-react";

import { api, DEMO_MODE, setToken } from "@/lib/api";
import type { TokenResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, full_name: fullName };
      const res = await api<TokenResponse>(`/api/v1/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setToken(res.access_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function launchDemo() {
    setError("");
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/api/v1/demo/start", { method: "POST" });
      setToken(res.access_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start demo");
      setBusy(false);
    }
  }

  if (DEMO_MODE) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="items-center text-center">
            <Bot className="mb-2 h-10 w-10 text-primary" />
            <CardTitle>OpsPilot AI — Live Demo</CardTitle>
            <CardDescription>
              A real, working instance pre-loaded with a simulated production incident.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                Your own sandboxed session — nothing you do is visible to anyone else.
              </li>
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                Seeded with real logs: SSH brute-force, Sysmon, Kubernetes and AWS CloudTrail.
              </li>
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                Everything resets automatically when your session ends.
              </li>
            </ul>
            <Button className="w-full" size="lg" onClick={launchDemo} disabled={busy}>
              <Play className="h-4 w-4" />
              {busy ? "Provisioning your sandbox…" : "Launch demo"}
            </Button>
            {error && <p className="text-center text-sm text-red-400">{error}</p>}
            <p className="text-center text-xs text-muted-foreground">
              Powered by the open-source{" "}
              <a
                href="https://github.com/omrzk/opspilot-ai"
                className="text-primary underline underline-offset-2"
                target="_blank"
                rel="noreferrer"
              >
                OpsPilot AI
              </a>{" "}
              project.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <Bot className="mb-2 h-10 w-10 text-primary" />
          <CardTitle>OpsPilot AI</CardTitle>
          <CardDescription>
            {mode === "login" ? "Sign in to your workspace" : "Create your account"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            {mode === "register" && (
              <Input
                placeholder="Full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
              />
            )}
            <Input
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <Input
              type="password"
              required
              minLength={8}
              placeholder="Password (min 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>
          <button
            className="mt-4 w-full text-center text-sm text-muted-foreground hover:text-foreground"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login"
              ? "No account yet? Register"
              : "Already have an account? Sign in"}
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
