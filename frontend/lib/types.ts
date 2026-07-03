export interface User {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta: { model?: string; sources?: RagSource[] };
  created_at: string;
}

export interface RagSource {
  title: string;
  doc_type: string;
  score: number;
}

export interface Upload {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  source_type: string;
  status: "pending" | "parsing" | "parsed" | "failed";
  record_count: number;
  error: string;
  created_at: string;
}

export interface LogEvent {
  id: string;
  timestamp: string | null;
  source: string;
  host: string;
  severity: string;
  event_id: string;
  message: string;
  raw: Record<string, unknown>;
}

export interface AffectedSystem {
  name: string;
  role?: string;
  evidence?: string;
}

export interface RemediationStep {
  step?: number;
  action: string;
  rationale?: string;
}

export interface Analysis {
  id: string;
  upload_id: string;
  status: "queued" | "running" | "completed" | "failed";
  model: string;
  summary: string;
  root_cause: string;
  severity: string;
  confidence: number;
  affected_systems: AffectedSystem[];
  remediation: RemediationStep[];
  scripts: { powershell?: string; bash?: string; terraform?: string; ansible?: string };
  evidence: string[];
  error: string;
  created_at: string;
  completed_at: string | null;
}

export type ReportKind =
  | "incident_report"
  | "executive_summary"
  | "technical_report"
  | "postmortem"
  | "runbook";

export interface Report {
  id: string;
  kind: ReportKind;
  title: string;
  content_md: string;
  status: "queued" | "running" | "completed" | "failed";
  error: string;
  analysis_id: string | null;
  incident_id: string | null;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  analysis_id: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  doc_type: string;
  source: string;
  status: string;
}

export interface SearchResult {
  document_id: string;
  title: string;
  doc_type: string;
  score: number;
  content: string;
}
