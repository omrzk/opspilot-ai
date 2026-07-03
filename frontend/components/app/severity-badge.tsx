import { Badge } from "@/components/ui/badge";

const VARIANTS: Record<string, "critical" | "error" | "warning" | "info" | "muted" | "success"> = {
  critical: "critical",
  high: "error",
  error: "error",
  medium: "warning",
  warning: "warning",
  low: "info",
  info: "info",
  informational: "muted",
  debug: "muted",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge variant={VARIANTS[severity] ?? "muted"}>{severity}</Badge>;
}

const STATUS_VARIANTS: Record<string, "success" | "warning" | "error" | "info" | "muted"> = {
  parsed: "success",
  completed: "success",
  resolved: "success",
  closed: "muted",
  parsing: "warning",
  running: "warning",
  queued: "info",
  pending: "info",
  open: "warning",
  investigating: "warning",
  mitigated: "info",
  failed: "error",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANTS[status] ?? "muted"}>{status}</Badge>;
}
