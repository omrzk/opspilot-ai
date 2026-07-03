"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { FileText, Siren } from "lucide-react";

import { api, formatDate } from "@/lib/api";
import type { Analysis, ReportKind } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceBar } from "@/components/app/confidence";
import { SeverityBadge, StatusBadge } from "@/components/app/severity-badge";
import { Shell } from "@/components/app/shell";

const SCRIPT_TABS: { key: keyof Analysis["scripts"]; label: string }[] = [
  { key: "powershell", label: "PowerShell" },
  { key: "bash", label: "Bash" },
  { key: "terraform", label: "Terraform" },
  { key: "ansible", label: "Ansible" },
];

const REPORT_KINDS: { kind: ReportKind; label: string }[] = [
  { kind: "incident_report", label: "Incident report" },
  { kind: "executive_summary", label: "Executive summary" },
  { kind: "technical_report", label: "Technical report" },
  { kind: "postmortem", label: "Postmortem" },
  { kind: "runbook", label: "Runbook" },
];

export default function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState("");

  const refresh = useCallback(() => {
    api<Analysis>(`/api/v1/analyses/${id}`).then(setAnalysis).catch(() => {});
  }, [id]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function createReport(kind: ReportKind) {
    setBusy(kind);
    try {
      await api("/api/v1/reports", {
        method: "POST",
        body: JSON.stringify({ kind, analysis_id: id }),
      });
      router.push("/reports");
    } finally {
      setBusy("");
    }
  }

  async function createIncident() {
    if (!analysis) return;
    setBusy("incident");
    try {
      await api("/api/v1/incidents", {
        method: "POST",
        body: JSON.stringify({
          title: analysis.summary.slice(0, 200) || "Incident from analysis",
          description: analysis.root_cause,
          severity: ["critical", "high", "medium", "low"].includes(analysis.severity)
            ? analysis.severity
            : "medium",
          analysis_id: id,
        }),
      });
      router.push("/incidents");
    } finally {
      setBusy("");
    }
  }

  if (!analysis) {
    return (
      <Shell>
        <div className="p-6 text-muted-foreground">Loading analysis…</div>
      </Shell>
    );
  }

  const scripts = SCRIPT_TABS.filter(({ key }) => (analysis.scripts[key] ?? "").trim());
  const running = analysis.status === "queued" || analysis.status === "running";

  return (
    <Shell>
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold">Analysis</h1>
              <SeverityBadge severity={analysis.severity} />
              <StatusBadge status={analysis.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {analysis.model && `Model: ${analysis.model} · `}
              Created {formatDate(analysis.created_at)}
              {analysis.completed_at && ` · Completed ${formatDate(analysis.completed_at)}`}
            </p>
          </div>
          {analysis.status === "completed" && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={createIncident} disabled={!!busy}>
                <Siren className="h-4 w-4" /> Open incident
              </Button>
              {REPORT_KINDS.map(({ kind, label }) => (
                <Button
                  key={kind}
                  variant="secondary"
                  size="sm"
                  disabled={!!busy}
                  onClick={() => createReport(kind)}
                >
                  <FileText className="h-4 w-4" />
                  {busy === kind ? "Queuing…" : label}
                </Button>
              ))}
            </div>
          )}
        </div>

        {running && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              The AI is analyzing your logs… this page refreshes automatically.
            </CardContent>
          </Card>
        )}
        {analysis.status === "failed" && (
          <Card className="border-red-900">
            <CardContent className="py-6 text-sm text-red-400">{analysis.error}</CardContent>
          </Card>
        )}

        {analysis.status === "completed" && (
          <>
            <div className="grid gap-4 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base">Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <p>{analysis.summary}</p>
                  <div>
                    <h3 className="mb-1 font-medium">Probable root cause</h3>
                    <p className="text-muted-foreground">{analysis.root_cause}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Confidence</CardTitle>
                </CardHeader>
                <CardContent>
                  <ConfidenceBar value={analysis.confidence} />
                  <p className="mt-3 text-xs text-muted-foreground">
                    How strongly the evidence in the logs supports the identified root cause.
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Affected systems ({analysis.affected_systems.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {analysis.affected_systems.map((s, i) => (
                    <div key={i} className="rounded-md border p-3">
                      <div className="font-medium">{s.name}</div>
                      {s.role && <div className="text-xs text-muted-foreground">{s.role}</div>}
                      {s.evidence && <div className="mt-1 text-xs">{s.evidence}</div>}
                    </div>
                  ))}
                  {analysis.affected_systems.length === 0 && (
                    <p className="text-muted-foreground">None identified.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Remediation plan</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {analysis.remediation.map((r, i) => (
                    <div key={i} className="flex gap-3 rounded-md border p-3">
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
                        {r.step ?? i + 1}
                      </div>
                      <div>
                        <div>{r.action}</div>
                        {r.rationale && (
                          <div className="mt-1 text-xs text-muted-foreground">{r.rationale}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  {analysis.remediation.length === 0 && (
                    <p className="text-muted-foreground">No remediation needed.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {scripts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Generated scripts</CardTitle>
                </CardHeader>
                <CardContent>
                  <Tabs defaultValue={scripts[0].key}>
                    <TabsList>
                      {scripts.map(({ key, label }) => (
                        <TabsTrigger key={key} value={key}>
                          {label}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    {scripts.map(({ key }) => (
                      <TabsContent key={key} value={key}>
                        <pre className="overflow-x-auto rounded-md border bg-black/40 p-4 text-xs">
                          <code>{analysis.scripts[key]}</code>
                        </pre>
                      </TabsContent>
                    ))}
                  </Tabs>
                </CardContent>
              </Card>
            )}

            {analysis.evidence.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Evidence</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1 text-xs">
                    {analysis.evidence.map((e, i) => (
                      <li key={i} className="rounded bg-muted/50 px-2 py-1 font-mono">
                        {e}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
