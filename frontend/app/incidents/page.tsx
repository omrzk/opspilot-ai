"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";

import { api, formatDate } from "@/lib/api";
import type { Incident } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

const STATUSES = ["open", "investigating", "mitigated", "resolved", "closed"];
const SEVERITIES = ["critical", "high", "medium", "low", "informational"];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");

  const refresh = useCallback(() => {
    api<Incident[]>("/api/v1/incidents").then(setIncidents).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await api("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify({ title, description, severity }),
    });
    setOpen(false);
    setTitle("");
    setDescription("");
    setSeverity("medium");
    refresh();
  }

  async function setStatus(incident: Incident, status: string) {
    await api(`/api/v1/incidents/${incident.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  return (
    <Shell>
      <div className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Incidents</h1>
            <p className="text-sm text-muted-foreground">
              Track ongoing issues and link them to AI analyses and reports.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4" /> New incident
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New incident</DialogTitle>
              </DialogHeader>
              <form onSubmit={create} className="space-y-3">
                <Input
                  required
                  placeholder="Title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <Textarea
                  placeholder="Description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                />
                <div className="flex flex-wrap gap-2">
                  {SEVERITIES.map((s) => (
                    <button type="button" key={s} onClick={() => setSeverity(s)}>
                      <span className={severity === s ? "" : "opacity-40"}>
                        <SeverityBadge severity={s} />
                      </span>
                    </button>
                  ))}
                </div>
                <Button type="submit" className="w-full">
                  Create incident
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Incident</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Opened</TableHead>
              <TableHead>Set status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {incidents.map((i) => (
              <TableRow key={i.id}>
                <TableCell>
                  <div className="font-medium">{i.title}</div>
                  {i.description && (
                    <div className="line-clamp-2 text-xs text-muted-foreground">
                      {i.description}
                    </div>
                  )}
                  {i.analysis_id && (
                    <Link
                      href={`/analyses/${i.analysis_id}`}
                      className="text-xs text-primary hover:underline"
                    >
                      View linked analysis →
                    </Link>
                  )}
                </TableCell>
                <TableCell>
                  <SeverityBadge severity={i.severity} />
                </TableCell>
                <TableCell>
                  <StatusBadge status={i.status} />
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDate(i.created_at)}</TableCell>
                <TableCell>
                  <select
                    className="rounded-md border border-input bg-background px-2 py-1 text-xs"
                    value={i.status}
                    onChange={(e) => setStatus(i, e.target.value)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
            {incidents.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  No incidents recorded.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </Shell>
  );
}
