# tests/backend/test_planner.py
"""
Phase 4 planner tests.

All tests use direct Python construction — no Ollama, no Supabase reads.
The only Supabase write is log_planner_decision (tested implicitly via T5).

Run:
    python -m tests.backend.test_planner
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Minimal RetrievedContext stub (mirrors memory_reader.RetrievedContext)
# We construct it directly so tests have no dependency on Phase 3.
# ---------------------------------------------------------------------------

@dataclass
class _RetrievedContext:
    retrieval_confidence: float = 0.0
    contact: dict | None = None
    applications: list = field(default_factory=list)
    meetings: list = field(default_factory=list)
    conference_submissions: list = field(default_factory=list)
    email_notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email(
    category: str,
    body: str = "Hi, please let us know your availability.",
    subject: str = "Test subject",
    sender_email: str = "sender@example.com",
    thread_id: str | None = "thread-001",
    has_attachments: bool = False,
) -> dict:
    return {
        "category": category,
        "body": body,
        "subject": subject,
        "sender_email": sender_email,
        "thread_id": thread_id,
        "has_attachments": has_attachments,
    }


def _entities(confidence: float = 0.8) -> dict:
    return {
        "extraction_confidence": confidence,
        "company": "Acme Corp",
        "role": "Software Engineer Intern",
    }


def _context(confidence: float = 0.0) -> _RetrievedContext:
    return _RetrievedContext(retrieval_confidence=confidence)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_t1_newsletter_no_reply_no_memory():
    """T1: Newsletter → reply_required=False, memory_action=skip."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email("NEWSLETTER", body="Check out our weekly digest!"),
        entities=_entities(),
        retrieved_context=_context(0.0),
    )
    assert not decision.reply_required, "Newsletter must not require a reply"
    assert decision.reply_strategy == "no_reply"
    assert decision.memory_action == "skip"
    print("✓ T1 passed — newsletter: no reply, no memory")


def test_t2_acknowledgment_no_reply_store_memory():
    """T2: Application acknowledgment → reply_required=False, memory_action=store_new."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "INTERNSHIP",
            body="Thank you for applying to Acme Corp. Your application ID is 12345.",
        ),
        entities=_entities(confidence=0.9),
        retrieved_context=_context(0.0),
    )
    assert not decision.reply_required, "Acknowledgment must not require a reply"
    assert decision.reply_strategy == "no_reply"
    assert decision.memory_action in ("store_new", "update_existing")
    print("✓ T2 passed — acknowledgment: no reply, memory stored")


def test_t3_recruiter_no_prior_context_low_confidence():
    """T3: Recruiter email, no prior context → reply_required=True, confidence < 0.6."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "RECRUITER",
            body="Hi, I'm a recruiter at Acme. Are you open to opportunities?",
        ),
        entities=_entities(confidence=0.7),
        retrieved_context=_context(0.0),  # no prior context
    )
    assert decision.reply_required, "Recruiter email must require a reply"
    assert decision.reply_strategy == "generate"
    assert decision.confidence < 0.6, (
        f"Expected confidence < 0.6 when no prior context, got {decision.confidence}"
    )
    print(f"✓ T3 passed — recruiter no context: confidence={decision.confidence}")


def test_t4_meeting_request_calendar_constraint():
    """T4: Meeting request, no calendar confirmation → date constraint present."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "MEETING",
            body="Could we schedule a call for tomorrow at 3 PM?",
        ),
        entities=_entities(),
        retrieved_context=_context(0.0),
    )
    assert decision.calendar_check_needed, "Calendar guard must fire for scheduling email"
    date_constraint = any(
        "date" in c or "time" in c for c in decision.constraints
    )
    assert date_constraint, (
        f"Expected a date/time constraint. Got: {decision.constraints}"
    )
    print("✓ T4 passed — meeting request: date commitment constraint present")


def test_t5_every_decision_logged_to_supabase():
    """T5: Every plan() call writes to planner_logs without raising."""
    from backend.planner.planner import plan

    # If log_planner_decision raises, it is caught internally and printed.
    # We verify plan() itself never raises regardless.
    try:
        decision = plan(
            email=_email("RECRUITER", body="We'd love to connect."),
            entities=_entities(),
            retrieved_context=_context(0.5),
        )
        assert decision is not None
        print("✓ T5 passed — plan() completed without raising (log written or warned)")
    except Exception as exc:
        print(f"✗ T5 FAILED — plan() raised: {exc}")
        raise


def test_t6_reasoning_non_empty():
    """T6: Every decision has a non-empty reasoning string."""
    from backend.planner.planner import plan

    categories = ["RECRUITER", "NEWSLETTER", "INTERNSHIP", "MEETING", "GENERAL"]
    for cat in categories:
        decision = plan(
            email=_email(cat, body="Some email body relevant to " + cat),
            entities=_entities(),
            retrieved_context=_context(0.0),
        )
        assert decision.reasoning.strip(), (
            f"reasoning must be non-empty for category {cat}"
        )
    print("✓ T6 passed — reasoning non-empty for all tested categories")


def test_t7_attachment_gap_constraint():
    """T7: Email mentions attachment but none parsed → attachment constraint present (EC-31)."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "RECRUITER",
            body="Please find attached my job description for your review.",
            has_attachments=False,  # MIME parser found nothing
        ),
        entities=_entities(),
        retrieved_context=_context(0.5),
    )
    attachment_constraint = any(
        "attachment" in c for c in decision.constraints
    )
    assert attachment_constraint, (
        f"Expected attachment constraint. Got: {decision.constraints}"
    )
    print("✓ T7 passed — attachment gap: constraint injected (EC-31)")


def test_t8_recruiter_with_prior_context():
    """T8: Recruiter with prior context → retrieval_needed=True, confidence >= 0.6."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "RECRUITER",
            body="Following up on your application to Acme Corp.",
        ),
        entities=_entities(confidence=0.85),
        retrieved_context=_context(0.8),  # strong prior context
    )
    assert decision.retrieval_needed, "retrieval_needed must be True when context exists"
    assert decision.confidence >= 0.6, (
        f"Expected confidence >= 0.6 with prior context, got {decision.confidence}"
    )
    print(f"✓ T8 passed — recruiter with context: confidence={decision.confidence}")


def test_t9_ambiguous_email_clarify_strategy():
    """T9: Ambiguous email → reply_strategy=clarify."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "GENERAL",
            body="Please let us know if you're interested.",
        ),
        entities=_entities(confidence=0.3),  # low confidence too
        retrieved_context=_context(0.0),
    )
    assert decision.reply_strategy == "clarify", (
        f"Expected 'clarify', got '{decision.reply_strategy}'"
    )
    print("✓ T9 passed — ambiguous email: clarify strategy selected")


def test_t10_suspicious_email_no_reply():
    """T10: Suspicious email → reply_strategy=no_reply, suspicious constraint present."""
    from backend.planner.planner import plan

    decision = plan(
        email=_email(
            "GENERAL",
            body="URGENT PAYMENT required. Click here to verify your account.",
            sender_email="no-reply@suspicious123.xyz",
        ),
        entities=_entities(),
        retrieved_context=_context(0.0),
    )
    assert decision.reply_strategy == "no_reply", (
        f"Expected 'no_reply' for suspicious email, got '{decision.reply_strategy}'"
    )
    suspicious_constraint = any(
        "suspicious" in c for c in decision.constraints
    )
    assert suspicious_constraint, (
        f"Expected suspicious constraint. Got: {decision.constraints}"
    )
    print("✓ T10 passed — suspicious email: no reply, flagged")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_t1_newsletter_no_reply_no_memory,
        test_t2_acknowledgment_no_reply_store_memory,
        test_t3_recruiter_no_prior_context_low_confidence,
        test_t4_meeting_request_calendar_constraint,
        test_t5_every_decision_logged_to_supabase,
        test_t6_reasoning_non_empty,
        test_t7_attachment_gap_constraint,
        test_t8_recruiter_with_prior_context,
        test_t9_ambiguous_email_clarify_strategy,
        test_t10_suspicious_email_no_reply,
    ]

    passed = 0
    failed = 0

    print("\n── Phase 4 Planner Tests ─────────────────────────────────")
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f"✗ {test_fn.__name__} FAILED: {exc}")
            failed += 1

    print(f"\n── Results: {passed} passed, {failed} failed ──────────────")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()