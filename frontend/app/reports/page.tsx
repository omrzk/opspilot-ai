"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw, Trash2 } from "lucide-react";

import { API_URL, api, formatDate, getToken } from "@/lib/api";
import type { Report } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Markdown } from "@/components/app/markdown";
import { StatusBadge } from "@/components/app/severity-badge";
import { Shell } from "@/components/app/shell";

const KIND_LABELS: Record<string, string> = {
  incident_report: "Incident report",
  executive_summary: "Executive summary",
  technical_report: "Technical report",
  postmortem: "Postmortem",
  runbook: "Runbook",
};

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [viewing, setViewing] = useState<Report | null>(null);

  const refresh = useCallback(() => {
    api<Report[]>("/api/v1/reports").then(setReports).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function remove(id: string) {
    await api(`/api/v1/reports/${id}`, { method: "DELETE" });
    refresh();
  }

  async function download(report: Report) {
    const res = await fetch(`${API_URL}/api/v1/reports/${report.id}/download`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.title || report.kind}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Shell>
      <div className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Reports</h1>
            <p className="text-sm text-muted-foreground">
              AI-written incident reports, summaries, postmortems and runbooks. Generate them
              from a completed analysis.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {reports.map((r) => (
              <TableRow key={r.id}>
                <TableCell>
                  <button
                    className="text-left text-primary hover:underline disabled:text-muted-foreground"
                    disabled={r.status !== "completed"}
                    onClick={() => setViewing(r)}
                  >
                    {r.title || KIND_LABELS[r.kind]}
                  </button>
                  {r.error && <div className="text-xs text-red-400">{r.error}</div>}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{KIND_LABELS[r.kind] ?? r.kind}</Badge>
                </TableCell>
                <TableCell>
                  <StatusBadge status={r.status} />
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDate(r.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <button
                      className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                      disabled={r.status !== "completed"}
                      onClick={() => download(r)}
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <button
                      className="text-muted-foreground hover:text-red-400"
                      onClick={() => remove(r.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {reports.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  No reports yet. Open a completed analysis to generate one.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        <Dialog open={!!viewing} onOpenChange={(open) => !open && setViewing(null)}>
          <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{viewing?.title}</DialogTitle>
            </DialogHeader>
            {viewing && <Markdown>{viewing.content_md}</Markdown>}
          </DialogContent>
        </Dialog>
      </div>
    </Shell>
  );
}
