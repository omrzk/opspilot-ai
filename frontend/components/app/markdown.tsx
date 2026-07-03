"use client";

import ReactMarkdown from "react-markdown";

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-ops">
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}
