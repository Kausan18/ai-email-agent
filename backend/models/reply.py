from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ---------------------------------------------------------------------------
# GenerationStrategy
# ---------------------------------------------------------------------------
# Which strategy produced this draft.
# V1 only uses BASE_MODEL.
# V2 adds FINE_TUNED.
# V3 adds RAG and HYBRID.
#
# Storing this on every draft means the comparison page (/email/:id/comparison)
# in V3 can show all three side by side with their strategy labeled.
# ---------------------------------------------------------------------------

class GenerationStrategy(str, Enum):
    BASE_MODEL  = "base_model"    # V1 — Mistral 7B via Ollama, no fine-tuning
    FINE_TUNED  = "fine_tuned"    # V2
    RAG         = "rag"           # V3
    HYBRID      = "hybrid"        # V3


# ---------------------------------------------------------------------------
# DraftReply
# ---------------------------------------------------------------------------
# The output of the inference module.
# Represents one generated draft before the user has reviewed it.
#
# Fields:
#   email_id        — links back to the CanonicalEmail this is a reply to
#   subject         — reply subject line (usually "Re: <original subject>")
#   body            — the generated reply text
#   strategy        — which generation strategy produced this
#   prompt_used     — the exact prompt sent to the model (stored for
#                     debugging and future prompt tuning)
#   model           — which model generated this (e.g. "mistral:7b-instruct")
#   generated_at    — timestamp of generation
#   latency_ms      — how long generation took in milliseconds
#                     (used in V3 evaluation metrics)
# ---------------------------------------------------------------------------

class DraftReply(BaseModel):
    email_id:     str
    subject:      str
    body:         str
    strategy:     GenerationStrategy  = GenerationStrategy.BASE_MODEL
    prompt_used:  Optional[str]       = None
    model:        str                 = "mistral:7b-instruct"
    generated_at: datetime            = Field(default_factory=datetime.utcnow)
    latency_ms:   Optional[float]     = None


# ---------------------------------------------------------------------------
# ApprovalAction
# ---------------------------------------------------------------------------
# What the user can do with a draft on the dashboard.
#
# APPROVED  — user liked it as-is, send it
# EDITED    — user modified the draft, send the edited version
# REJECTED  — user discarded the draft entirely, no email sent
#
# This enum is used both in the API request body and stored in the
# feedback log (V2/V3 will use this as training signal).
# ---------------------------------------------------------------------------

class ApprovalAction(str, Enum):
    APPROVED = "approved"
    EDITED   = "edited"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# ApprovalRequest
# ---------------------------------------------------------------------------
# The payload the frontend sends to POST /review/approve.
#
# Fields:
#   email_id      — which email this decision is for
#   action        — what the user decided
#   edited_body   — only populated if action == EDITED
#                   contains the user's modified version of the draft
#
# In V2/V3 this whole object gets stored as a feedback record and
# becomes a training signal for the router and fine-tuned model.
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    email_id:     str
    action:       ApprovalAction
    edited_body:  Optional[str] = None

    # Validation: if action is EDITED, edited_body must be present
    def model_post_init(self, __context):
        if self.action == ApprovalAction.EDITED and not self.edited_body:
            raise ValueError("edited_body is required when action is EDITED")


# ---------------------------------------------------------------------------
# ApprovalResponse
# ---------------------------------------------------------------------------
# What the backend returns after processing an approval decision.
# ---------------------------------------------------------------------------

class ApprovalResponse(BaseModel):
    email_id: str
    action:   ApprovalAction
    message:  str                  # Human-readable confirmation
    sent:     bool = False         # True only when Gmail send succeeds (V1 end)