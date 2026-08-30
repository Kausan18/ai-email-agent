import { EmailDetail, InboxSummary, ApprovalAction, ApprovalResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getInbox(needsReply?: boolean): Promise<InboxSummary[]> {
  const query = needsReply !== undefined ? `?needs_reply=${needsReply}` : "";
  const res = await fetch(`${API_URL}/api/inbox${query}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load inbox (${res.status})`);
  return res.json();
}

export async function getEmailDetail(id: string): Promise<EmailDetail> {
  const res = await fetch(`${API_URL}/api/email/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load email ${id} (${res.status})`);
  return res.json();
}

export async function submitApproval(
  emailId: string,
  action: ApprovalAction,
  editedBody?: string
): Promise<ApprovalResponse> {
  const res = await fetch(`${API_URL}/api/review/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email_id: emailId, action, edited_body: editedBody ?? null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Approval request failed (${res.status})`);
  }
  return res.json();
}