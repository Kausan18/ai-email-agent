"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Pencil, X } from "lucide-react";
import { submitApproval } from "@/lib/api";
import { DraftReply } from "@/lib/types";

export function DraftPanel({ emailId, draft }: { emailId: string; draft: DraftReply }) {
  const router = useRouter();
  const [body, setBody] = useState(draft.body);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const hasEdits = body !== draft.body;

  async function handleAction(action: "approved" | "edited" | "rejected") {
    setBusy(true);
    setStatus(null);
    try {
      const res = await submitApproval(emailId, action, action === "edited" ? body : undefined);
      setStatus(res.message);
      router.refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Draft reply</h3>
        <span className="font-mono text-[11px] text-textMuted">
          {draft.model}
          {draft.latency_ms ? ` · ${Math.round(draft.latency_ms)}ms` : ""}
        </span>
      </div>

      <p className="mb-2 text-xs text-textMuted">{draft.subject}</p>

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={14}
        className="mb-4 flex-1 resize-none rounded-md border border-border bg-bg p-3 text-sm leading-relaxed text-text focus:border-accent focus:outline-none"
      />

      <div className="flex items-center gap-2">
        <button
          disabled={busy}
          onClick={() => handleAction(hasEdits ? "edited" : "approved")}
          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Check size={14} />
          {hasEdits ? "Save & approve" : "Approve"}
        </button>

        <button
          disabled={busy}
          onClick={() => handleAction("rejected")}
          className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-textMuted transition-colors hover:bg-surfaceHover hover:text-text disabled:opacity-50"
        >
          <X size={14} />
          Reject
        </button>

        {hasEdits && (
          <span className="flex items-center gap-1 font-mono text-[11px] text-category-reminder">
            <Pencil size={11} /> edited
          </span>
        )}
      </div>

      {status && <p className="mt-3 text-xs text-textMuted">{status}</p>}
    </div>
  );
}