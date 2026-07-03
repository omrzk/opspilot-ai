"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, FileText, Siren, Upload as UploadIcon } from "lucide-react";

import { api, formatDate } from "@/lib/api";
import type { Analysis, Incident, Report, Upload } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge, StatusBadge } from "@/components/app/severity-badge";
import { Shell } from "@/components/app/shell";

export default function DashboardPage() {
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [reports, setReports] = useState<Report[]>([]);

  useEffect(() => {
    api<Upload[]>("/api/v1/uploads").then(setUploads).catch(() => {});
    api<Analysis[]>("/api/v1/analyses").then(setAnalyses).catch(() => {});
    api<Incident[]>("/api/v1/incidents").then(setIncidents).catch(() => {});
    api<Report[]>("/api/v1/reports").then(setReports).catch(() => {});
  }, []);

  const openIncidents = incidents.filter((i) => !["resolved", "closed"].includes(i.status));
  const stats = [
    { label: "Log uploads", value: uploads.length, icon: UploadIcon, href: "/uploads" },
    { label: "AI analyses", value: analyses.length, icon: Activity, href: "/analyses" },
    { label: "Open incidents", value: openIncidents.length, icon: Siren, href: "/incidents" },
    { label: "Reports", value: reports.length, icon: FileText, href: "/reports" },
  ];

  return (
    <Shell>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Your infrastructure intelligence at a glance.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map(({ label, value, icon: Icon, href }) => (
            <Link key={label} href={href}>
              <Card className="transition-colors hover:border-primary/50">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {label}
                  </CardTitle>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{value}</div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent analyses</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {analyses.slice(0, 6).map((a) => (
                <Link
                  key={a.id}
                  href={`/analyses/${a.id}`}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-accent/50"
                >
                  <span className="truncate">{a.summary || `Analysis ${a.id.slice(0, 8)}`}</span>
                  <span className="ml-2 flex shrink-0 gap-2">
                    <SeverityBadge severity={a.severity} />
                    <StatusBadge status={a.status} />
                  </span>
                </Link>
              ))}
              {analyses.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No analyses yet. Upload a log file to get started.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Open incidents</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {openIncidents.slice(0, 6).map((i) => (
                <div
                  key={i.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                >
                  <div className="min-w-0">
                    <div className="truncate">{i.title}</div>
                    <div className="text-xs text-muted-foreground">{formatDate(i.created_at)}</div>
                  </div>
                  <span className="ml-2 flex shrink-0 gap-2">
                    <SeverityBadge severity={i.severity} />
                    <StatusBadge status={i.status} />
                  </span>
                </div>
              ))}
              {openIncidents.length === 0 && (
                <p className="text-sm text-muted-foreground">No open incidents. 🎉</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Shell>
  );
}
