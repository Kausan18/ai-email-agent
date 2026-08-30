import Link from "next/link";
import { getInbox } from "@/lib/api";
import { CategoryTag } from "@/components/CategoryTag";

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default async function FiledPage() {
  const emails = await getInbox(false);

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-lg font-semibold text-text">Filed</h1>
        <span className="font-mono text-xs text-textMuted">{emails.length} messages</span>
      </div>

      <p className="mb-4 text-xs text-textMuted">
        Newsletters, promotions, and automated acknowledgments the agent decided don&apos;t need a reply (EC-1 / EC-2).
      </p>

      <div className="overflow-hidden rounded-lg border border-border opacity-70">
        {emails.map((email, i) => (
          <Link
            key={email.id}
            href={`/email/${email.id}`}
            className={`flex items-center gap-4 px-4 py-3 transition-colors hover:bg-surfaceHover hover:opacity-100 ${
              i !== 0 ? "border-t border-border" : ""
            }`}
          >
            <div className="w-40 shrink-0 truncate text-sm text-textMuted">
              {email.sender_name ?? email.sender_email}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-text">{email.subject}</div>
            </div>
            <CategoryTag category={email.category} />
            <div className="w-24 shrink-0 text-right font-mono text-[11px] text-textMuted">
              {formatTimestamp(email.timestamp)}
            </div>
          </Link>
        ))}

        {emails.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-textMuted">
            Nothing filed yet.
          </div>
        )}
      </div>
    </div>
  );
}