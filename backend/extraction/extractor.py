"""
Entity extractor — the main entry point for Phase 2.

Flow:
  1. If category is in NO_EXTRACT_CATEGORIES → return None immediately.
  2. Build the category-specific prompt.
  3. Call Mistral via Ollama (same HTTP client pattern as V1).
  4. Parse the JSON response.
  5. Validate into the correct Pydantic schema.
  6. Attach extraction_confidence and return.

EC-21: if retrieval/parsing fails, fall back gracefully — never raise.
EC-29: prompts explicitly forbid inventing fields.
"""

import json
import logging
import httpx

from backend.extraction.schemas import (
    RecruiterEntity,
    ApplicationEntity,
    MeetingEntity,
    ConferenceEntity,
    GeneralEntity,
    EntityResult,
)
from backend.extraction.prompts import (
    build_prompt,
    NO_EXTRACT_CATEGORIES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — mirrors V1 Ollama client settings
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"          # updated to mistral-email-v2 after Phase 6 fine-tuning
OLLAMA_TIMEOUT = 60.0             # seconds; extraction prompts are short so this is generous


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _score_confidence(parsed: dict, category: str) -> float:
    """
    Derive a simple confidence score from how many fields were populated.

    Required fields per category — these are the ones we most care about.
    If all required fields are present → high confidence.
    If half are missing → medium.
    If most are missing → low.
    """
    required: dict[str, list[str]] = {
        "RECRUITER":  ["recruiter_name", "company", "role"],
        "INTERNSHIP": ["company", "role"],
        "MEETING":    ["title", "scheduled_time"],
        "CONFERENCE": ["conference_name", "paper_title"],
    }
    # General / fallback categories: always medium unless parsing failed
    key_fields = required.get(category.upper(), [])
    if not key_fields:
        return 0.6

    populated = sum(1 for f in key_fields if parsed.get(f) not in (None, "", []))
    ratio = populated / len(key_fields)

    if ratio >= 1.0:
        return 0.9
    elif ratio >= 0.5:
        return 0.6
    else:
        return 0.3


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def _call_ollama(system_prompt: str, user_prompt: str) -> str | None:
    """
    POST to Ollama and return the raw response text.
    Returns None on any network or HTTP error.

    Note: keep_alive is intentionally omitted — causes 500s on this Ollama version.
    stream is False so we get the full response in one shot.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,    # extraction must be deterministic
            "num_predict": 512,    # JSON objects are short; cap tokens
        },
    }
    try:
        response = httpx.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except httpx.HTTPStatusError as e:
        logger.error("Ollama HTTP error during extraction: %s", e)
        return None
    except httpx.RequestError as e:
        logger.error("Ollama connection error during extraction: %s", e)
        return None


# ---------------------------------------------------------------------------
# JSON parsing with fallback
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> dict | None:
    """
    Parse the model's raw output as JSON.

    Mistral occasionally wraps output in markdown code fences despite
    instructions. Strip them before parsing.
    Returns None if parsing ultimately fails.
    """
    if not raw:
        return None

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract the first {...} block as a last resort
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        logger.warning("JSON parse failed entirely. Raw output: %s", raw[:200])
        return None


# ---------------------------------------------------------------------------
# Schema hydration
# ---------------------------------------------------------------------------

def _hydrate(parsed: dict, category: str, confidence: float) -> EntityResult:
    """
    Validate the parsed dict into the correct Pydantic model.
    Falls back to GeneralEntity if the target model validation fails.
    """
    cat = category.upper()
    try:
        if cat == "RECRUITER":
            return RecruiterEntity(**parsed, extraction_confidence=confidence)
        elif cat == "INTERNSHIP":
            return ApplicationEntity(**parsed, extraction_confidence=confidence)
        elif cat == "MEETING":
            return MeetingEntity(**parsed, extraction_confidence=confidence)
        elif cat == "CONFERENCE":
            return ConferenceEntity(**parsed, extraction_confidence=confidence)
        else:
            return GeneralEntity(**parsed, extraction_confidence=confidence)
    except Exception as e:
        logger.warning("Pydantic validation failed for %s: %s. Falling back to GeneralEntity.", category, e)
        # Strip keys that GeneralEntity doesn't know about to avoid another validation error
        general_keys = {"sender_name", "sender_email", "topic", "action_items", "mentioned_dates", "notes"}
        safe = {k: v for k, v in parsed.items() if k in general_keys}
        return GeneralEntity(**safe, extraction_confidence=confidence * 0.5)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_entities(
    email_text: str,
    category: str,
    thread_id: str | None = None,
) -> EntityResult:
    """
    Extract structured entities from a classified email.

    Args:
        email_text:  The full plain-text body of the email.
        category:    The classifier output (RECRUITER, INTERNSHIP, MEETING, etc.)
        thread_id:   Optional Gmail thread ID — injected into MeetingEntity post-extraction.

    Returns:
        A typed Pydantic entity, or None for categories that need no extraction.
    """
    # EC-2: Skip newsletters and promotions entirely
    if category.upper() in NO_EXTRACT_CATEGORIES:
        logger.info("Category %s skipped — no extraction needed.", category)
        return None

    system_prompt, user_prompt = build_prompt(category, email_text)

    raw = _call_ollama(system_prompt, user_prompt)

    if raw is None:
        # Ollama unreachable — return a low-confidence GeneralEntity rather than crashing
        logger.error("Ollama call failed for category %s. Returning empty GeneralEntity.", category)
        return GeneralEntity(
            topic="[extraction failed — Ollama unavailable]",
            extraction_confidence=0.0,
        )

    parsed = _parse_json(raw)

    if parsed is None:
        # JSON parse failed completely — return raw text as a note
        logger.warning("JSON parse failed for category %s. Storing raw output as note.", category)
        return GeneralEntity(
            notes=raw[:1000],   # cap to avoid bloated records
            extraction_confidence=0.1,
        )

    confidence = _score_confidence(parsed, category)
    entity = _hydrate(parsed, category, confidence)

    # Inject thread_id into MeetingEntity — the LLM doesn't know this
    if isinstance(entity, MeetingEntity) and thread_id:
        entity.thread_id = thread_id

    logger.info(
        "Extracted %s entity for category=%s confidence=%.2f",
        type(entity).__name__,
        category,
        entity.extraction_confidence,
    )
    return entity