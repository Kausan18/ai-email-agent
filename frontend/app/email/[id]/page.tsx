import { getEmailDetail } from "@/lib/api";
import { CategoryTag } from "@/components/CategoryTag";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { DraftPanel } from "@/components/DraftPanel";

export default async function EmailDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const detail = await getEmailDetail(id);
  const { email } = detail;

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-8 py-10">
      {/* Original email */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <div className="mb-4 flex items-center gap-2">
          <CategoryTag category={detail.category} />
          <ConfidenceBar confidence={detail.confidence} />
        </div>

        <p className="mb-5 font-mono text-xs italic text-textMuted">{"// " + detail.reason}</p>

        <h2 className="mb-1 text-base font-semibold text-text">{email.subject}</h2>
        <p className="mb-4 text-sm text-textMuted">
          {email.sender.name ?? email.sender.email} &lt;{email.sender.email}&gt;
        </p>

        <div className="whitespace-pre-wrap text-sm leading-relaxed text-text/90">{email.body_html ? (
  <iframe
    srcDoc={email.body_html}
    sandbox=""
    className="h-125 w-full rounded-md border border-border bg-white"
    title={`email-body-${email.id}`}
  />
) : (
  <div className="whitespace-pre-wrap text-sm leading-relaxed text-text/90">{email.body}</div>
)}</div>
      </div>

      {/* Draft panel */}
      <div className="rounded-lg border border-border bg-surface p-6">
        {detail.reply_required ? (
          detail.draft ? (
            <DraftPanel emailId={email.id} draft={detail.draft} />
          ) : (
            <p className="text-sm text-textMuted">No draft available.</p>
          )
        ) : (
          <p className="text-sm text-textMuted">
            No reply required for this email — classified as{" "}
            <span className="font-mono text-xs">{detail.category}</span>.
          </p>
        )}
      </div>
    </div>
  );
}