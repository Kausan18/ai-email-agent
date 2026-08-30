export interface EmailSender {
  name: string | null;
  email: string;
}

export interface CanonicalEmail {
  id: string;
  thread_id: string | null;
  sender: EmailSender;
  recipients: string[];
  subject: string;
  body: string;
  body_html?: string | null;
  timestamp: string;
  is_reply: boolean;
}

export type EmailCategory =
  | "recruiter"
  | "internship"
  | "meeting"
  | "professor"
  | "conference"
  | "reminder"
  | "newsletter"
  | "promotion"
  | "personal"
  | "unknown";

export interface InboxSummary {
  id: string;
  sender_name: string | null;
  sender_email: string;
  subject: string;
  timestamp: string;
  category: EmailCategory;
  confidence: number;
  reply_required: boolean;
  has_draft: boolean;
}

export type GenerationStrategy = "base_model" | "fine_tuned" | "rag" | "hybrid";

export interface DraftReply {
  email_id: string;
  subject: string;
  body: string;
  strategy: GenerationStrategy;
  model: string;
  generated_at: string;
  latency_ms: number | null;
}

export interface EmailDetail {
  email: CanonicalEmail;
  category: EmailCategory;
  reply_required: boolean;
  confidence: number;
  reason: string;
  draft: DraftReply | null;
}

export type ApprovalAction = "approved" | "edited" | "rejected";

export interface ApprovalResponse {
  email_id: string;
  action: ApprovalAction;
  message: string;
  sent: boolean;
}