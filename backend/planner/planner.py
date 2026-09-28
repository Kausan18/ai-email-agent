# backend/planner/planner.py
"""
plan() — the single public function of the planner module.

Takes already-processed upstream outputs and emits a PlannerDecision.
No Ollama calls. No Supabase reads. Pure deterministic logic.

Inputs:
    email           dict  — ParsedEmail-shaped dict from ingestion/parser
    entities        dict  — EntityResult.model_dump() from Phase 2 extraction
    retrieved_context — RetrievedContext from Phase 3 memory_reader

Output:
    PlannerDecision — written to planner_logs, returned to caller
"""

from __future__ import annotations
import traceback
from typing import Any

from backend.planner.decision_schema import PlannerDecision
from backend.planner.edge_case_rules import (
    is_newsletter_or_promotion,
    is_acknowledgment,
    is_suspicious,
    is_ambiguous,
    calendar_guard_needed,
    attachment_gap_detected,
    retrieval_is_weak,
    is_thread_continuation,
    has_prior_context,
    is_unknown_sender,
    compute_planner_confidence,
)
from backend.memory import db


def plan(
    email: dict[str, Any],
    entities: dict[str, Any],
    retrieved_context: Any,  # RetrievedContext dataclass from memory_reader
) -> PlannerDecision:
    """
    Core planner.

    Priority order (higher = evaluated first, short-circuits lower):
      1. SUSPICIOUS   → no_reply, flag
      2. NO-REPLY     → no_reply (newsletter/promo = skip memory;
                                  acknowledgment = store_new)
      3. AMBIGUOUS    → clarify
      4. CALENDAR     → generate + date constraint
      5. ATTACHMENT   → generate + attachment constraint
      6. WEAK RETRIEVAL → generate + no-hallucinate constraint
      7. NORMAL       → generate
    """

    # ── Unpack inputs ──────────────────────────────────────────────────
    category: str = email.get("category", "GENERAL").upper()
    email_body: str = email.get("body", "") or ""
    subject: str = email.get("subject", "") or ""
    sender_email: str = email.get("sender_email", "") or ""
    thread_id: str | None = email.get("thread_id")
    has_attachments: bool = bool(email.get("has_attachments", False))

    entity_confidence: float = float(entities.get("extraction_confidence", 0.5))

    retrieval_confidence: float = float(
        getattr(retrieved_context, "retrieval_confidence", 0.0)
    )

    constraints: list[str] = []
    reply_required = True
    reply_strategy: str = "generate"
    memory_action: str = "store_new"
    calendar_check_needed = False
    retrieval_needed = False
    reasoning = ""

    # ── Priority 1: SUSPICIOUS (EC-32) ────────────────────────────────
    if is_suspicious(email_body, sender_email, subject):
        reply_required = False
        reply_strategy = "no_reply"
        memory_action = "skip"
        constraints = ["do not reply — email flagged as potentially suspicious"]
        reasoning = (
            "This email contains suspicious language patterns. "
            "It has been flagged for user review and no reply will be generated."
        )
        confidence = 0.1
        decision = PlannerDecision(
            reply_required=reply_required,
            reply_strategy=reply_strategy,
            memory_action=memory_action,
            retrieval_needed=False,
            retrieval_confidence=0.0,
            calendar_check_needed=False,
            constraints=constraints,
            confidence=confidence,
            generation_strategy="fine_tuned",
            reasoning=reasoning,
        )
        _log(email, decision)
        return decision

    # ── Priority 2a: NEWSLETTER / PROMOTION (EC-2) ────────────────────
    if is_newsletter_or_promotion(category):
        reply_required = False
        reply_strategy = "no_reply"
        memory_action = "skip"
        reasoning = (
            f"Email classified as {category}. "
            "No reply required and no information will be stored."
        )
        decision = PlannerDecision(
            reply_required=False,
            reply_strategy="no_reply",
            memory_action="skip",
            retrieval_needed=False,
            retrieval_confidence=0.0,
            calendar_check_needed=False,
            constraints=[],
            confidence=0.95,
            generation_strategy="fine_tuned",
            reasoning=reasoning,
        )
        _log(email, decision)
        return decision

    # ── Priority 2b: ACKNOWLEDGMENT (EC-1, EC-5, EC-6) ───────────────
    if is_acknowledgment(category, email_body):
        # Determine memory action: new record or update if thread continues
        if is_thread_continuation(retrieval_confidence, thread_id):
            memory_action = "update_existing"
        else:
            memory_action = "store_new"

        reasoning = (
            f"This is an automated acknowledgment ({category}). "
            "No reply will be generated, but the relevant details "
            "have been extracted and stored in memory."
        )
        decision = PlannerDecision(
            reply_required=False,
            reply_strategy="no_reply",
            memory_action=memory_action,
            retrieval_needed=False,
            retrieval_confidence=retrieval_confidence,
            calendar_check_needed=False,
            constraints=[],
            confidence=0.90,
            generation_strategy="fine_tuned",
            reasoning=reasoning,
        )
        _log(email, decision)
        return decision

    # ── Priority 3: AMBIGUOUS (EC-4) ──────────────────────────────────
    if is_ambiguous(email_body, entity_confidence):
        confidence = compute_planner_confidence(
            entity_confidence=entity_confidence,
            retrieval_confidence=retrieval_confidence,
            calendar_guard=False,
            weak_retrieval=False,
            ambiguous=True,
        )
        reasoning = (
            "The intent of this email is unclear — either the language is vague "
            "or the extractor could not identify sufficient context. "
            "A clarification response is recommended instead of a direct reply."
        )
        decision = PlannerDecision(
            reply_required=True,
            reply_strategy="clarify",
            memory_action="store_new",
            retrieval_needed=False,
            retrieval_confidence=retrieval_confidence,
            calendar_check_needed=False,
            constraints=["ask for clarification before making any commitments"],
            confidence=confidence,
            generation_strategy="fine_tuned",
            reasoning=reasoning,
        )
        _log(email, decision)
        return decision

    # ── From here: reply_strategy = "generate" ────────────────────────
    # Evaluate all remaining guards and accumulate constraints.

    # ── Priority 4: CALENDAR GUARD (EC-14–17, EC-33) ──────────────────
    calendar_guard = calendar_guard_needed(email_body, category)
    if calendar_guard:
        calendar_check_needed = True
        constraints.append(
            "do not commit to any specific date or time — "
            "calendar availability has not been confirmed"
        )

    # ── Priority 5: ATTACHMENT GAP (EC-31) ────────────────────────────
    if attachment_gap_detected(email_body, has_attachments):
        constraints.append(
            "do not reference or claim to have reviewed any attachments — "
            "no attachment data was received"
        )

    # ── Priority 6: WEAK RETRIEVAL (EC-21, EC-22) ─────────────────────
    weak_retrieval = retrieval_is_weak(retrieval_confidence)
    if weak_retrieval:
        constraints.append(
            "do not reference any specific details, names, or facts "
            "not explicitly present in the email being replied to"
        )
    else:
        retrieval_needed = True

    # ── Memory action ──────────────────────────────────────────────────
    if is_thread_continuation(retrieval_confidence, thread_id):
        memory_action = "update_existing"
    elif is_unknown_sender(retrieval_confidence):
        # EC-18: cold contact — store basic note, no structured entity
        memory_action = "store_new"
    else:
        memory_action = "store_new"

    # ── Confidence ─────────────────────────────────────────────────────
    confidence = compute_planner_confidence(
        entity_confidence=entity_confidence,
        retrieval_confidence=retrieval_confidence,
        calendar_guard=calendar_guard,
        weak_retrieval=weak_retrieval,
        ambiguous=False,
    )

    # ── Reasoning ─────────────────────────────────────────────────────
    context_phrase = (
        "Prior context was found in memory and will be used to ground the reply."
        if has_prior_context(retrieval_confidence)
        else "No prior context was found — reply will be based on the email alone."
    )
    constraint_phrase = (
        f" {len(constraints)} constraint(s) applied." if constraints else ""
    )
    reasoning = (
        f"Email classified as {category}. "
        f"{context_phrase}"
        f"{constraint_phrase}"
    )

    decision = PlannerDecision(
        reply_required=True,
        reply_strategy="generate",
        memory_action=memory_action,
        retrieval_needed=retrieval_needed,
        retrieval_confidence=retrieval_confidence,
        calendar_check_needed=calendar_check_needed,
        constraints=constraints,
        confidence=confidence,
        generation_strategy="fine_tuned",
        reasoning=reasoning,
    )
    _log(email, decision)
    return decision


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log(email: dict[str, Any], decision: PlannerDecision) -> None:
    """
    Write planner decision to Supabase planner_logs table.
    Errors are printed but never re-raised — logging must never
    crash the pipeline.
    """
    try:
        thread_id = email.get("thread_id") or email.get("id", "unknown")
        db.log_planner_decision(thread_id, decision.model_dump())
    except Exception:
        print("[planner] WARNING: failed to write planner_log — continuing anyway")
        traceback.print_exc()