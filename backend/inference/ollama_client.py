import time
import requests
from requests.exceptions import RequestException

from backend.models.email import ClassifiedEmail
from backend.models.reply import DraftReply, GenerationStrategy
from backend.prompts.prompt_builder import build_prompt
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Ollama Client — V1
# ---------------------------------------------------------------------------
# Responsibility: take a ClassifiedEmail, build its prompt, send it to the
# local Ollama server, and return a DraftReply.
#
# V1 uses a single strategy (GenerationStrategy.BASE_MODEL) and a single
# model (settings.OLLAMA_MODEL, i.e. mistral:7b-instruct). No retrieval,
# no fine-tuning — this module is intentionally dumb. All the reasoning
# happened upstream in the classifier and prompt_builder.
#
# Why /api/generate and not /api/chat:
#   prompt_builder already produces one fully-formed instruction string
#   (system instructions + email content baked into the template), so
#   there's no multi-turn chat history to manage. /api/generate is the
#   simpler, more direct fit for that shape of input.
#
# stream=False:
#   V1 dashboard shows a draft only after it's fully generated (no
#   token-by-token streaming UI yet). Keeping this synchronous keeps
#   ollama_client.py simple; streaming can be added later without
#   touching any other module, since the return type stays DraftReply.
# ---------------------------------------------------------------------------


class OllamaClientError(Exception):
    """Raised when Ollama is unreachable or returns an unexpected response."""
    pass


def _build_reply_subject(original_subject: str) -> str:
    """
    Prefixes 'Re: ' unless the subject already has it (case-insensitive),
    to avoid 'Re: Re: Re: ...' chains on long threads.
    """
    stripped = original_subject.strip()
    if stripped.lower().startswith("re:"):
        return stripped
    return f"Re: {stripped}"


def _call_ollama(prompt: str) -> tuple[str, float]:
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
 # keep model resident between clicks during a review session
        "options": {
            "temperature": settings.TEMPERATURE,
            "num_predict": settings.MAX_TOKENS,
        },
    }

    start = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=300)  # was 120 — cold load can exceed this on partial GPU offload
        response.raise_for_status()
    except RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        raise OllamaClientError(
            f"Could not reach Ollama at {settings.OLLAMA_BASE_URL}. "
            f"Is 'ollama serve' running and is '{settings.OLLAMA_MODEL}' pulled?"
        ) from e
    latency_ms = (time.perf_counter() - start) * 1000

    data = response.json()
    reply_text = data.get("response")
    if reply_text is None:
        logger.error(f"Ollama returned unexpected payload: {data}")
        raise OllamaClientError("Ollama response missing 'response' field.")

    return reply_text.strip(), latency_ms

def generate_reply(classified: ClassifiedEmail) -> DraftReply:
    """
    Full V1 inference step: ClassifiedEmail -> DraftReply.

    1. Build the prompt (prompt_builder handles category vs clarification logic)
    2. Send it to Ollama
    3. Wrap the result in a DraftReply, preserving the prompt used for
       debugging and the exact latency for future V3 evaluation metrics
    """
    email = classified.email
    prompt = build_prompt(classified)

    logger.info(f"Email {email.id}: sending prompt to Ollama ({settings.OLLAMA_MODEL})")

    body_text, latency_ms = _call_ollama(prompt)

    draft = DraftReply(
        email_id=email.id,
        subject=_build_reply_subject(email.subject),
        body=body_text,
        strategy=GenerationStrategy.BASE_MODEL,
        prompt_used=prompt,
        model=settings.OLLAMA_MODEL,
        latency_ms=latency_ms,
    )

    logger.info(f"Email {email.id}: draft generated in {latency_ms:.0f}ms")
    return draft

def warm_up() -> None:
    """
    Sends a trivial prompt to Ollama once at server startup so the model
    is already loaded into memory before the first real request. Without
    this, whichever email you open first pays the full cold-load latency —
    which is exactly what caused the 503 you saw.
    """
    try:
        _call_ollama("Reply with OK.")
        logger.info("Ollama warm-up complete — model loaded into memory.")
    except OllamaClientError as e:
        logger.warning(f"Ollama warm-up failed, will retry lazily on first request: {e}")