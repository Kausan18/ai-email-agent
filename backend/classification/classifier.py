from backend.models.email import CanonicalEmail, ClassifiedEmail, EmailCategory
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rule-Based Classifier — V1
# ---------------------------------------------------------------------------
# This is intentionally NOT ML-based. It's keyword + sender-domain matching.
#
# Why rules instead of a model call here?
#   - Zero inference cost for something this simple
#   - Fully deterministic and debuggable (you can see exactly why a
#     category was chosen via the `reason` field)
#   - Gives us a working baseline pipeline before fine-tuning exists (V2)
#
# The classifier's job has TWO outputs, not one:
#   1. category        — what kind of email is this?
#   2. reply_required   — should the agent even bother drafting a reply?
#
# EC-1 / EC-2 from EDGE_CASES.md: automated acknowledgments and
# newsletters/promotions should NEVER get a generated reply. We filter
# those out here, before they ever reach the prompt builder or Ollama.
# This saves inference calls on the majority of real-world inbox noise.
# ---------------------------------------------------------------------------


# Domains / sender patterns that indicate automated, no-reply-needed mail
NO_REPLY_SENDER_PATTERNS = ["no-reply", "noreply", "newsletter", "notifications"]

# Keywords that strongly indicate a newsletter/promotion (EC-2)
NEWSLETTER_KEYWORDS = ["unsubscribe", "weekly digest", "newsletter", "call for papers"]

# Keywords that indicate an automated acknowledgment (EC-1 / EC-5)
ACKNOWLEDGMENT_KEYWORDS = [
    "application received", "application submitted", "successfully submitted",
    "payment successful", "submission received", "thank you for applying"
]

# Keywords per category — checked against subject + body (lowercased)
CATEGORY_KEYWORDS = {
    EmailCategory.RECRUITER:   ["recruiter", "opportunity", "position", "internship", "hiring", "role"],
    EmailCategory.PROFESSOR:   ["professor", "prof.", "assignment", "project update", "course", "semester"],
    EmailCategory.MEETING:     ["meeting", "confirming", "schedule", "call at", "let's meet", "meet up"],
    EmailCategory.CONFERENCE:  ["conference", "paper", "submission", "attendance", "call for papers"],
    EmailCategory.INTERNSHIP:  ["internship", "intern position", "application"],
    EmailCategory.REMINDER:    ["reminder", "don't forget", "follow up", "following up"],
}

# Ambiguous phrases that should trigger low-confidence clarification (EC-4)
AMBIGUOUS_PHRASES = [
    "let us know if you're interested", "let us know if you are interested",
    "still interested", "following up on my previous message"
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_email(email: CanonicalEmail) -> ClassifiedEmail:
    """
    Classifies a CanonicalEmail into a category, decides whether a reply
    is required, and assigns a confidence score + human-readable reason.

    Confidence scale (V1, rule-based — refined later by the V3 confidence engine):
        1.0  — clear, unambiguous match (sender pattern or strong keyword)
        0.5  — ambiguous, ties to EC-4 (generate clarification, not a reply)
        0.0  — no reply needed at all (newsletter / promotion / ack)
    """

    sender_email = email.sender.email.lower()
    subject      = email.subject.lower()
    body         = email.body.lower()
    full_text    = f"{subject} {body}"

    
    # ---- Step 1: Application/submission acknowledgments (EC-1, EC-5) ----
    if _contains_any(full_text, ACKNOWLEDGMENT_KEYWORDS):
        logger.info(f"Email {email.id} → INTERNSHIP acknowledgment (no reply, store memory later)")
        return ClassifiedEmail(
            email=email,
            category=EmailCategory.INTERNSHIP,
            reply_required=False,
            confidence=1.0,
            reason="Automated acknowledgment detected — no reply needed."
        )

    # ---- Step 2: Automated / no-reply sources (EC-1, EC-2) ----
        if _contains_any(sender_email, NO_REPLY_SENDER_PATTERNS) or _contains_any(full_text, NEWSLETTER_KEYWORDS):
            logger.info(f"Email {email.id} → NEWSLETTER/PROMOTION (no reply)")
            return ClassifiedEmail(
                email=email,
                category=EmailCategory.NEWSLETTER,
                reply_required=False,
                confidence=1.0,
                reason="Sender pattern or content matches newsletter/automated source."
            )
    

    # ---- Step 3: Ambiguous emails (EC-4) ----
    if _contains_any(full_text, AMBIGUOUS_PHRASES):
        logger.warning(f"Email {email.id} → UNKNOWN, ambiguous phrasing detected (low confidence)")
        return ClassifiedEmail(
            email=email,
            category=EmailCategory.UNKNOWN,
            reply_required=True,
            confidence=0.5,
            reason="Ambiguous phrasing detected — clarification reply recommended instead of assuming context."
        )

    # ---- Step 4: Category keyword matching ----
    for category, keywords in CATEGORY_KEYWORDS.items():
        if _contains_any(full_text, keywords):
            logger.info(f"Email {email.id} → {category.value} (reply required)")
            return ClassifiedEmail(
                email=email,
                category=category,
                reply_required=True,
                confidence=1.0,
                reason=f"Matched keywords associated with '{category.value}' category."
            )

    # ---- Step 5: Fallback — unknown, but human-sent, so still reply ----
    logger.warning(f"Email {email.id} → PERSONAL/UNKNOWN fallback, generic reply required")
    return ClassifiedEmail(
        email=email,
        category=EmailCategory.PERSONAL,
        reply_required=True,
        confidence=0.5,
        reason="No strong category match — defaulting to personal/generic reply."
    )