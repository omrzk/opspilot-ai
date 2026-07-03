"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import type { KnowledgeDocument, SearchResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Shell } from "@/components/app/shell";

const DOC_TYPES = ["runbook", "documentation", "incident_history", "note"];

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [docType, setDocType] = useState("documentation");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const refresh = useCallback(() => {
    api<KnowledgeDocument[]>("/api/v1/knowledge/documents").then(setDocuments).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 6000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await api("/api/v1/knowledge/documents", {
      method: "POST",
      body: JSON.stringify({ title, text, doc_type: docType }),
    });
    setOpen(false);
    setTitle("");
    setText("");
    refresh();
  }

  async function remove(id: string) {
    await api(`/api/v1/knowledge/documents/${id}`, { method: "DELETE" });
    refresh();
  }

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await api<{ results: SearchResult[] }>("/api/v1/knowledge/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      setResults(res.results);
    } finally {
      setSearching(false);
    }
  }

  return (
    <Shell>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Knowledge Base</h1>
            <p className="text-sm text-muted-foreground">
              Runbooks, documentation and incident history the AI uses as context (RAG).
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4" /> Add document
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add document</DialogTitle>
              </DialogHeader>
              <form onSubmit={create} className="space-y-3">
                <Input
                  required
                  placeholder="Title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <div className="flex gap-2">
                  {DOC_TYPES.map((t) => (
                    <button type="button" key={t} onClick={() => setDocType(t)}>
                      <Badge variant={docType === t ? "info" : "muted"}>{t}</Badge>
                    </button>
                  ))}
                </div>
                <Textarea
                  required
                  placeholder="Paste the document content (Markdown or plain text)…"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={12}
                />
                <Button type="submit" className="w-full">
                  Ingest into knowledge base
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Semantic search</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={search} className="flex gap-2">
              <Input
                placeholder="e.g. how do we recover a failed etcd node?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Button type="submit" disabled={searching}>
                <Search className="h-4 w-4" /> {searching ? "Searching…" : "Search"}
              </Button>
            </form>
            {results && (
              <div className="mt-4 space-y-2">
                {results.map((r, i) => (
                  <div key={i} className="rounded-md border p-3 text-sm">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="font-medium">{r.title}</span>
                      <Badge variant="muted">{r.doc_type}</Badge>
                      <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                        {(r.score * 100).toFixed(0)}% match
                      </span>
                    </div>
                    <p className="line-clamp-4 text-xs text-muted-foreground">{r.content}</p>
                  </div>
                ))}
                {results.length === 0 && (
                  <p className="text-sm text-muted-foreground">No matches found.</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((d) => (
            <Card key={d.id}>
              <CardContent className="flex items-start justify-between gap-2 p-4">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{d.title}</div>
                  <div className="mt-1 flex gap-2">
                    <Badge variant="muted">{d.doc_type}</Badge>
                    <Badge variant={d.status.startsWith("ready") ? "success" : "warning"}>
                      {d.status === "ready_no_embeddings" ? "ready (no vectors)" : d.status}
                    </Badge>
                  </div>
                </div>
                <button
                  className="shrink-0 text-muted-foreground hover:text-red-400"
                  onClick={() => remove(d.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </CardContent>
            </Card>
          ))}
          {documents.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No documents yet. Add runbooks and docs so the AI can cite them.
            </p>
          )}
        </div>
      </div>
    </Shell>
  );
}
