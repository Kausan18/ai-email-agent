from tests.backend.test_classifier import load_mock_emails
from backend.classification.classifier import classify_email
from backend.prompts.prompt_builder import build_prompt, build_prompt_safe

# Mock planner decisions / retrieved context for visual testing only —
# not real planner/memory-reader output. Swap for real objects once
# Phase 4/3 outputs are wired into this script's pipeline.
from backend.planner.decision_schema import PlannerDecision
from backend.memory.memory_reader import RetrievedContext


def _mock_decision(confidence=0.85, constraints=None):
    return PlannerDecision(
        reply_required=True,
        reply_strategy="generate",
        memory_action="skip",
        retrieval_needed=True,
        retrieval_confidence=0.6,
        calendar_check_needed=False,
        constraints=constraints or [],
        confidence=confidence,
        generation_strategy="fine_tuned",
        reasoning="mock for visual inspection",
    )


def _mock_context(summary=""):
    return RetrievedContext(retrieval_summary=summary)


def run():
    emails = load_mock_emails()

    for email in emails:
        classified = classify_email(email)

        print("=" * 90)
        print(f"Email ID: {classified.email.id}  |  Category: {classified.category.value}  |  Confidence: {classified.confidence}")

        if not classified.reply_required:
            print(">> No reply required — prompt builder skipped.")
            continue

        print(">> V1 PROMPT:\n")
        print(build_prompt(classified))

        # Adjust these per-email as needed to sanity check different cases:
        decision = _mock_decision(
            confidence=0.3,
            constraints=["Do not commit to a specific date or time."],
        )
        context = _mock_context("Applied to Google for SWE Intern via LinkedIn on Sept 12.")

        print("\n>> V2 PROMPT:\n")
        print(build_prompt_safe(classified, decision, context))

    print("=" * 90)


if __name__ == "__main__":
    run()