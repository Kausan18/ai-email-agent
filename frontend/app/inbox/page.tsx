import Link from "next/link";
import { getInbox } from "@/lib/api";
import { CategoryTag } from "@/components/CategoryTag";
import { ConfidenceBar } from "@/components/ConfidenceBar";

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default async function InboxPage() {
  const emails = await getInbox();

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-lg font-semibold text-text">Inbox</h1>
        <span className="font-mono text-xs text-textMuted">{emails.length} messages</span>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        {emails.map((email, i) => (
          <Link
            key={email.id}
            href={`/email/${email.id}`}
            className={`flex items-center gap-4 px-4 py-3 transition-colors hover:bg-surfaceHover ${
              i !== 0 ? "border-t border-border" : ""
            } ${email.reply_required ? "" : "opacity-60"}`}
          >
            <div className="w-40 shrink-0 truncate text-sm text-textMuted">
              {email.sender_name ?? email.sender_email}
            </div>

            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-text">{email.subject}</div>
            </div>

            <CategoryTag category={email.category} />
            <ConfidenceBar confidence={email.confidence} />

            {email.has_draft && (
              <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[10px] uppercase text-accent">
                Draft
              </span>
            )}
            {!email.reply_required && (
              <span className="font-mono text-[10px] uppercase text-textMuted">No reply</span>
            )}

            <div className="w-24 shrink-0 text-right font-mono text-[11px] text-textMuted">
              {formatTimestamp(email.timestamp)}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}