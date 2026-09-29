from pathlib import Path

from backend.models.email import ClassifiedEmail, EmailCategory
from backend.config import settings, BASE_DIR
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt Builder — V1
# ---------------------------------------------------------------------------
# Responsibility: take a ClassifiedEmail (email + category + confidence)
# and produce ONE plain string — the exact prompt that will be sent to
# Ollama. This module does NOT call the model. It only builds text.
#
# Why templates live in separate .txt files instead of inline Python strings:
#   - You can tune wording for one category without touching Python code
#   - Non-technical review of tone/instructions is easier in plain text
#   - Keeps prompt_builder.py itself simple: load file -> fill placeholders
#
# Two-tier selection logic:
#   1. If confidence is LOW (EC-4: ambiguous emails) -> always use
#      clarification.txt, regardless of category. We do NOT want the
#      model inventing context when the classifier itself wasn't sure.
#   2. Otherwise -> pick template matching category, falling back to
#      generic.txt if no dedicated template exists for that category.
# ---------------------------------------------------------------------------


TEMPLATES_DIR = BASE_DIR / "backend" / "prompts" / "templates"

# Maps category -> template filename.
# Categories not listed here (newsletter, promotion, internship-ack, unknown)
# never reach this function anyway, since reply_required=False stops them
# earlier in the pipeline (except UNKNOWN, which is handled via confidence).
CATEGORY_TEMPLATE_MAP = {
    EmailCategory.RECRUITER:  "recruiter.txt",
    EmailCategory.INTERNSHIP: "recruiter.txt",   # internship replies use recruiter tone
    EmailCategory.MEETING:    "meeting.txt",
    EmailCategory.PROFESSOR:  "professor.txt",
    EmailCategory.CONFERENCE: "conference.txt",
    EmailCategory.PERSONAL:   "generic.txt",
    EmailCategory.REMINDER:   "generic.txt",
}

CLARIFICATION_TEMPLATE = "clarification.txt"
FALLBACK_TEMPLATE      = "generic.txt"

# TODO: move to config/.env once we support multiple users
USER_NAME = "Kaustubh"


def _load_template(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(classified: ClassifiedEmail) -> str:
    """
    Builds the final prompt string for a ClassifiedEmail.

    Selection logic:
        confidence < LOW_CONFIDENCE_THRESHOLD  -> clarification.txt (EC-4)
        else                                    -> category-specific template
                                                    (falls back to generic.txt)
    """

    email = classified.email

    # ---- Step 1: Low confidence overrides category selection (EC-4) ----
    if classified.confidence < settings.LOW_CONFIDENCE_THRESHOLD or classified.category == EmailCategory.UNKNOWN:
        template_name = CLARIFICATION_TEMPLATE
        logger.info(f"Email {email.id}: low confidence ({classified.confidence}) -> using clarification template")
    else:
        template_name = CATEGORY_TEMPLATE_MAP.get(classified.category, FALLBACK_TEMPLATE)
        logger.info(f"Email {email.id}: category={classified.category.value} -> using {template_name}")

    template = _load_template(template_name)

    # ---- Step 2: Fill placeholders with real email data ----
    prompt = template.format(
        user_name=USER_NAME,
        sender_name=email.sender.name or "there",
        sender_email=email.sender.email,
        subject=email.subject,
        body=email.body,
    )

    return prompt

# ---------------------------------------------------------------------------
# Prompt Builder — V2
# ---------------------------------------------------------------------------
# Responsibility: wrap the V1 template output with three extra blocks built
# from PlannerDecision and RetrievedContext — context, constraints, and a
# confidence hedge — then prepend them above the category template text.
#
# V2 does NOT touch template files or the V1 selection logic (low-confidence
# -> clarification.txt, else category -> template). It reuses build_prompt()
# as-is and wraps the string it returns.
#
# Failure mode: if anything in the V2 path raises, we log it and fall back
# to plain V1 output. The pipeline must never crash on a prompt-builder bug.
# ---------------------------------------------------------------------------

from backend.planner.decision_schema import PlannerDecision
from backend.memory.memory_reader import RetrievedContext


def _build_context_block(retrieved_context: "RetrievedContext | None") -> str:
    """
    Renders retrieval_summary as a '## Context from memory' block.
    Returns "" if there's nothing usable — no empty header, no placeholder
    filler when nothing was retrieved (EC-21: don't invent details).
    """
    if retrieved_context is None:
        return ""

    summary = (retrieved_context.retrieval_summary or "").strip()
    if not summary:
        return ""

    return f"## Context from memory\n{summary}\n"


def _build_constraints_block(planner_decision: "PlannerDecision | None") -> str:
    """
    Renders planner_decision.constraints verbatim as a bullet list.
    These strings are the hallucination guard — never paraphrase them.
    Returns "" if there are no constraints.
    """
    if planner_decision is None or not planner_decision.constraints:
        return ""

    bullets = "\n".join(f"- {c}" for c in planner_decision.constraints)
    return f"## Constraints\n{bullets}\n"


def _build_confidence_instruction(planner_decision: "PlannerDecision | None") -> str:
    """
    Returns a hedging instruction line when planner confidence is below
    the same threshold V1 uses to route to clarification.txt. Returns ""
    for high-confidence decisions — no instruction needed.
    """
    if planner_decision is None:
        return ""

    if planner_decision.confidence < settings.LOW_CONFIDENCE_THRESHOLD:
        return (
            "## Confidence note\n"
            "Confidence in the available context is low. Hedge rather than "
            "asserting facts you are not certain of, and avoid firm "
            "commitments (dates, times, decisions) unless explicitly "
            "confirmed above.\n"
        )

    return ""


def build_prompt_v2(
    classified: ClassifiedEmail,
    planner_decision: PlannerDecision,
    retrieved_context: RetrievedContext | None,
) -> str:
    """
    Builds the V2 prompt: context + constraints + confidence-hedge blocks,
    prepended above the V1 template output. Raises on failure — callers
    should catch and fall back to build_prompt(classified) directly.
    """
    base_prompt = build_prompt(classified)

    blocks = [
        _build_context_block(retrieved_context),
        _build_constraints_block(planner_decision),
        _build_confidence_instruction(planner_decision),
    ]
    prefix = "\n".join(b for b in blocks if b)

    if not prefix:
        return base_prompt

    return f"{prefix}\n{base_prompt}"


def build_prompt_safe(
    classified: ClassifiedEmail,
    planner_decision: PlannerDecision | None = None,
    retrieved_context: RetrievedContext | None = None,
) -> str:
    """
    Single entry point for callers going forward.

    If planner_decision is provided, attempts the V2 prompt (context +
    constraints + confidence hedge, prepended over the V1 template).
    On any exception, logs the traceback and falls back to plain V1 output
    via build_prompt(classified) — matches the never-silent-except pattern
    used in memory_writer.py and planner.py.
    """
    if planner_decision is not None:
        try:
            return build_prompt_v2(classified, planner_decision, retrieved_context)
        except Exception:
            logger.exception(
                f"Email {classified.email.id}: V2 prompt build failed, falling back to V1"
            )

    return build_prompt(classified)