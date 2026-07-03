"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";

import { api, formatDate } from "@/lib/api";
import type { Analysis } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SeverityBadge, StatusBadge } from "@/components/app/severity-badge";
import { Shell } from "@/components/app/shell";

export default function AnalysesPage() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);

  const refresh = useCallback(() => {
    api<Analysis[]>("/api/v1/analyses").then(setAnalyses).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <Shell>
      <div className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">AI Analyses</h1>
            <p className="text-sm text-muted-foreground">
              Root-cause analyses generated from your log uploads.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Summary</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {analyses.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Link href={`/analyses/${a.id}`} className="text-primary hover:underline">
                    {a.summary?.slice(0, 120) || `Analysis ${a.id.slice(0, 8)}`}
                  </Link>
                  {a.error && <div className="text-xs text-red-400">{a.error}</div>}
                </TableCell>
                <TableCell>
                  <SeverityBadge severity={a.severity} />
                </TableCell>
                <TableCell>
                  <StatusBadge status={a.status} />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {a.status === "completed" ? `${Math.round(a.confidence * 100)}%` : "—"}
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDate(a.created_at)}</TableCell>
              </TableRow>
            ))}
            {analyses.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  No analyses yet. Open an upload and click “Analyze with AI”.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </Shell>
  );
}
