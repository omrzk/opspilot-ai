"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, Send, Trash2 } from "lucide-react";

import { api, formatDate, streamChat } from "@/lib/api";
import type { Conversation, Message, RagSource, Upload } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Markdown } from "@/components/app/markdown";
import { Shell } from "@/components/app/shell";

interface LocalMessage {
  role: "user" | "assistant";
  content: string;
  sources?: RagSource[];
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [attachedUploads, setAttachedUploads] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => {
    api<Conversation[]>("/api/v1/chat/conversations").then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    loadConversations();
    api<Upload[]>("/api/v1/uploads")
      .then((all) => setUploads(all.filter((u) => u.status === "parsed")))
      .catch(() => {});
  }, [loadConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function openConversation(id: string) {
    setActiveId(id);
    const detail = await api<Conversation & { messages: Message[] }>(
      `/api/v1/chat/conversations/${id}`
    );
    setMessages(
      detail.messages
        .filter((m) => m.role !== "system")
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.meta?.sources,
        }))
    );
  }

  function newConversation() {
    setActiveId(null);
    setMessages([]);
    setAttachedUploads([]);
  }

  async function deleteConversation(id: string) {
    await api(`/api/v1/chat/conversations/${id}`, { method: "DELETE" });
    if (id === activeId) newConversation();
    loadConversations();
  }

  async function send() {
    const message = input.trim();
    if (!message || streaming) return;
    setInput("");
    setStreaming(true);
    setMessages((prev) => [...prev, { role: "user", content: message }, { role: "assistant", content: "" }]);

    let sources: RagSource[] = [];
    try {
      await streamChat(
        {
          conversation_id: activeId ?? undefined,
          message,
          upload_ids: attachedUploads,
          use_rag: true,
        },
        {
          onMeta: (meta) => {
            if (!activeId) {
              setActiveId(meta.conversation_id);
              loadConversations();
            }
            sources = (meta.sources as RagSource[]) ?? [];
          },
          onDelta: (text) => {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                ...next[next.length - 1],
                content: next[next.length - 1].content + text,
              };
              return next;
            });
          },
          onError: (detail) => {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                role: "assistant",
                content: `**Error:** ${detail}`,
              };
              return next;
            });
          },
          onDone: () => {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], sources };
              return next;
            });
          },
        }
      );
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `**Error:** ${err instanceof Error ? err.message : "request failed"}`,
        };
        return next;
      });
    } finally {
      setStreaming(false);
      loadConversations();
    }
  }

  return (
    <Shell>
      <div className="flex h-full">
        <aside className="flex w-64 shrink-0 flex-col border-r">
          <div className="p-3">
            <Button variant="outline" size="sm" className="w-full" onClick={newConversation}>
              <Plus className="h-4 w-4" /> New chat
            </Button>
          </div>
          <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-2">
            {conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm",
                  c.id === activeId ? "bg-accent" : "hover:bg-accent/50"
                )}
                onClick={() => openConversation(c.id)}
              >
                <div className="min-w-0">
                  <div className="truncate">{c.title}</div>
                  <div className="text-xs text-muted-foreground">{formatDate(c.updated_at)}</div>
                </div>
                <button
                  className="ml-1 hidden shrink-0 text-muted-foreground hover:text-red-400 group-hover:block"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto p-6">
            {messages.length === 0 && (
              <div className="mx-auto mt-16 max-w-md text-center text-muted-foreground">
                <h2 className="mb-2 text-lg font-medium text-foreground">
                  Ask OpsPilot anything
                </h2>
                <p className="text-sm">
                  Troubleshoot incidents, explain log entries, generate PowerShell / Bash /
                  Terraform / Ansible, or attach a parsed log upload for context.
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-lg px-4 py-3",
                    m.role === "user" ? "bg-primary text-primary-foreground" : "border bg-card"
                  )}
                >
                  {m.role === "assistant" ? (
                    <>
                      <Markdown>{m.content || "…"}</Markdown>
                      {m.sources && m.sources.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1 border-t pt-2">
                          {m.sources.map((s, j) => (
                            <Badge key={j} variant="muted" title={`relevance ${s.score}`}>
                              {s.doc_type}: {s.title}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="whitespace-pre-wrap text-sm">{m.content}</div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t p-4">
            {uploads.length > 0 && (
              <div className="mb-2 flex flex-wrap items-center gap-1">
                <span className="mr-1 text-xs text-muted-foreground">Attach logs:</span>
                {uploads.slice(0, 8).map((u) => {
                  const attached = attachedUploads.includes(u.id);
                  return (
                    <button
                      key={u.id}
                      onClick={() =>
                        setAttachedUploads((prev) =>
                          attached ? prev.filter((id) => id !== u.id) : [...prev, u.id]
                        )
                      }
                    >
                      <Badge variant={attached ? "info" : "muted"}>{u.filename}</Badge>
                    </button>
                  );
                })}
              </div>
            )}
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Ask about your infrastructure… (Enter to send, Shift+Enter for newline)"
                className="min-h-[44px] flex-1 resize-none"
                rows={2}
              />
              <Button onClick={send} disabled={streaming || !input.trim()} className="self-end">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
