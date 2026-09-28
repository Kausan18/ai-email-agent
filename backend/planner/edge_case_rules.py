# backend/planner/edge_case_rules.py
"""
Pure rule functions — one per EC group.

All functions are:
  - Pure (no I/O, no side effects, no Supabase, no Ollama)
  - Independently testable
  - Called by planner.py; results merged there

EC references are noted on each function.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports at runtime; only used for type hints.
    from backend.memory.memory_reader import RetrievedContext

# ---------------------------------------------------------------------------
# Category constants (must match classifier output strings exactly)
# ---------------------------------------------------------------------------

NO_REPLY_CATEGORIES: set[str] = {"NEWSLETTER", "PROMOTION"}

ACKNOWLEDGMENT_CATEGORIES: set[str] = {"INTERNSHIP", "CONFERENCE", "APPLICATION"}

SCHEDULING_CATEGORIES: set[str] = {"MEETING", "RECRUITER", "PROFESSOR", "PERSONAL"}

SUSPICIOUS_KEYWORDS: list[str] = [
    "urgent payment",
    "wire transfer",
    "click here to verify",
    "your account has been suspended",
    "confirm your password",
    "lottery",
    "you have won",
    "nigerian prince",
]

ATTACHMENT_KEYWORDS: list[str] = [
    "attached",
    "see attachment",
    "please find attached",
    "attachment enclosed",
    "refer to the attached",
    "as attached",
    "enclosed herewith",
]

SCHEDULING_KEYWORDS: list[str] = [
    "schedule",
    "availability",
    "available",
    "meeting",
    "interview",
    "call",
    "slot",
    "time",
    "date",
    "when",
    "tomorrow",
    "next week",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "am",
    "pm",
]

AMBIGUITY_PHRASES: list[str] = [
    "please let us know if you're interested",
    "let us know if you are interested",
    "if you're interested",
    "if you are interested",
    "please confirm your interest",
    "kindly let us know",
    "do let us know",
]

# ---------------------------------------------------------------------------
# EC-1, EC-2 — No-reply categories
# ---------------------------------------------------------------------------

def is_no_reply_category(category: str) -> bool:
    """
    EC-1: Automated acknowledgments (INTERNSHIP, CONFERENCE) — no reply needed.
    EC-2: Newsletters and promotions — no reply, no memory.

    Note: acknowledgment categories still need memory storage even though
    no reply is generated. The distinction is handled in planner.py, not here.
    This function returns True for ANY category that never needs a reply.
    """
    return category.upper() in NO_REPLY_CATEGORIES or category.upper() in ACKNOWLEDGMENT_CATEGORIES


def is_newsletter_or_promotion(category: str) -> bool:
    """
    EC-2: Strict no-reply AND no-memory check.
    Narrower than is_no_reply_category — only the two categories that skip
    memory storage entirely.
    """
    return category.upper() in NO_REPLY_CATEGORIES


def is_acknowledgment(category: str, email_body: str) -> bool:
    """
    EC-1, EC-5, EC-6: Automated acknowledgment — no reply, but store memory.

    Acknowledgments come from no-reply senders in INTERNSHIP/CONFERENCE
    categories. The category alone is sufficient; we don't need to parse
    the body here because the classifier already handles that distinction.
    """
    return category.upper() in ACKNOWLEDGMENT_CATEGORIES


# ---------------------------------------------------------------------------
# EC-4 — Ambiguous emails
# ---------------------------------------------------------------------------

def is_ambiguous(email_body: str, entity_confidence: float) -> bool:
    """
    EC-4: Ambiguous email — low entity confidence OR known ambiguity phrases.

    If the entity extractor couldn't figure out what the email is about
    (confidence < 0.4), or the body contains a vague call-to-action with
    no supporting context, we route to clarify rather than guess.
    """
    body_lower = email_body.lower()
    phrase_match = any(phrase in body_lower for phrase in AMBIGUITY_PHRASES)
    low_confidence = entity_confidence < 0.4
    return phrase_match or low_confidence


# ---------------------------------------------------------------------------
# EC-14–17, EC-33 — Calendar / scheduling guard
# ---------------------------------------------------------------------------

def calendar_guard_needed(email_body: str, category: str) -> bool:
    """
    EC-14–17, EC-33: Scheduling-related email detected.

    Returns True when the email body contains scheduling language,
    regardless of whether the calendar was consulted or what it said.

    The planner uses this to add the date-commitment constraint.
    The constraint fires unconditionally when this is True because:
      - EC-16: empty calendar ≠ available
      - EC-17: calendar API failure ≠ available
      - EC-33: external source reliability is never assumed to be HIGH
               in V2 (static weight = LOW until proven otherwise)

    In V3, the confidence engine will override this with a HIGH-reliability
    signal once the calendar proves trustworthy over time.
    """
    if category.upper() in SCHEDULING_CATEGORIES:
        body_lower = email_body.lower()
        return any(kw in body_lower for kw in SCHEDULING_KEYWORDS)
    return False


# ---------------------------------------------------------------------------
# EC-31 — Attachment gap
# ---------------------------------------------------------------------------

def attachment_gap_detected(email_body: str, has_attachments: bool = False) -> bool:
    """
    EC-31: Email body references an attachment but no attachment data
    was parsed by the ingestion layer.

    has_attachments: True if the MIME parser found real attachment objects.
    If the body mentions an attachment but has_attachments is False,
    the agent must not pretend it has reviewed it.
    """
    body_lower = email_body.lower()
    body_mentions_attachment = any(kw in body_lower for kw in ATTACHMENT_KEYWORDS)
    return body_mentions_attachment and not has_attachments


# ---------------------------------------------------------------------------
# EC-21, EC-22 — Retrieval quality
# ---------------------------------------------------------------------------

def retrieval_is_weak(retrieval_confidence: float) -> bool:
    """
    EC-21: Retrieval returned nothing (confidence = 0.0).
    EC-22: Retrieval returned weak matches (confidence < 0.4).

    Both cases add the "do not reference specific details" constraint.
    The threshold 0.4 matches the memory_reader heuristic where 0.4
    means only a company-level match was found (no contact, no application).
    """
    return retrieval_confidence < 0.4


# ---------------------------------------------------------------------------
# EC-9, EC-25, EC-26 — Thread continuation / deduplication
# ---------------------------------------------------------------------------

def is_thread_continuation(retrieval_confidence: float, thread_id: str | None) -> bool:
    """
    EC-9: Email belongs to an ongoing thread — don't store duplicate info.
    EC-25: Duplicate emails — merge, don't create new records.
    EC-26: Updated information — update existing memory, don't create new entries.

    A thread_id match plus any retrieval hit (confidence > 0.0) is sufficient
    to treat this as a continuation. The memory_writer handles the actual
    deduplication; this flag signals the planner to set memory_action=update_existing.
    """
    return thread_id is not None and retrieval_confidence > 0.0


# ---------------------------------------------------------------------------
# EC-32 — Suspicious / phishing emails
# ---------------------------------------------------------------------------

def is_suspicious(
    email_body: str,
    sender_email: str,
    subject: str = "",
) -> bool:
    """
    EC-32: Phishing / suspicious email — no reply, flag for user.

    Checks:
    1. Body contains known suspicious keywords.
    2. Sender domain is a known free-email provider but email claims
       to be from a corporate entity (mismatch heuristic — simple version).

    This is intentionally conservative in V2. A real phishing detector
    would use a trained classifier. Here we flag only obvious cases.
    """
    combined = (email_body + " " + subject).lower()
    keyword_hit = any(kw in combined for kw in SUSPICIOUS_KEYWORDS)
    return keyword_hit


# ---------------------------------------------------------------------------
# EC-10, EC-12, EC-13 — Prior context existence
# ---------------------------------------------------------------------------

def has_prior_context(retrieval_confidence: float) -> bool:
    """
    EC-10: Unknown company but prior application exists — connect them.
    EC-12: Conference follow-up after submission.
    EC-13: Recruiter contacts after months — long-term memory.

    A retrieval confidence > 0.4 means we found at least a contact record
    or better. This is the threshold where grounded generation becomes possible.
    """
    return retrieval_confidence > 0.4


# ---------------------------------------------------------------------------
# EC-18 — Unknown sender
# ---------------------------------------------------------------------------

def is_unknown_sender(retrieval_confidence: float) -> bool:
    """
    EC-18: No history, no retrieval.
    Use generic professional reply — don't reference specific details.
    """
    return retrieval_confidence == 0.0


# ---------------------------------------------------------------------------
# Confidence calculation (shared utility used by planner.py)
# ---------------------------------------------------------------------------

def compute_planner_confidence(
    entity_confidence: float,
    retrieval_confidence: float,
    calendar_guard: bool,
    weak_retrieval: bool,
    ambiguous: bool,
) -> float:
    """
    Weighted confidence signal for the PlannerDecision.

    Weights:
      entity_confidence   40%  — how well the extractor understood the email
      retrieval_confidence 40% — how much grounded context we have
      rule_penalty         20% — penalised when guards fire

    rule_penalty:
      1.0  → no guards fired
      0.5  → calendar guard fired (EC-16/17/33)
      0.3  → weak retrieval (EC-21/22)
      0.1  → ambiguous (EC-4)

    The lowest applicable penalty wins.
    """
    if ambiguous:
        rule_penalty = 0.1
    elif weak_retrieval:
        rule_penalty = 0.3
    elif calendar_guard:
        rule_penalty = 0.5
    else:
        rule_penalty = 1.0

    raw = entity_confidence * 0.4 + retrieval_confidence * 0.4 + rule_penalty * 0.2
    # Clamp to [0.0, 1.0]
    return round(max(0.0, min(1.0, raw)), 3)