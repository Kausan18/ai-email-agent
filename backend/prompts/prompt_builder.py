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