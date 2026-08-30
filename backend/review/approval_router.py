import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.config import MOCK_DATA_PATH
from backend.models.email import CanonicalEmail, ClassifiedEmail
from backend.models.reply import DraftReply, ApprovalRequest, ApprovalResponse, ApprovalAction
from backend.classification.classifier import classify_email
from backend.inference.ollama_client import generate_reply, OllamaClientError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["review"])


# ---------------------------------------------------------------------------
# In-memory stores — V1 only.
# ---------------------------------------------------------------------------
# No Supabase yet (that's V2). The whole "inbox" is just the mock dataset,
# classified once at first access and cached in these dicts for the life
# of the server process. Restarting the server wipes drafts and decisions —
# fine for V1, since the point is to validate the pipeline shape, not
# persist state.
#
# _INBOX        — email_id -> ClassifiedEmail (loaded once from mock JSON)
# _DRAFTS       — email_id -> DraftReply (generated lazily, on first view)
# _FEEDBACK_LOG — append-only list of every approve/edit/reject decision.
#                 Not wired to anything yet, but this is exactly the shape
#                 V2/V3's feedback pipeline needs, so we start logging now.
# ---------------------------------------------------------------------------

_INBOX: dict[str, ClassifiedEmail] = {}
_DRAFTS: dict[str, DraftReply] = {}
_FEEDBACK_LOG: list[dict] = []


def _load_mock_inbox() -> None:
    """Loads emails.json, converts each to CanonicalEmail, classifies once,
    and caches the result. Called lazily on first request, not at import
    time — keeps this module side-effect-free until the app actually runs.
    """
    with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
        raw_emails = json.load(f)

    for raw in raw_emails:
        email = CanonicalEmail(**raw)
        classified = classify_email(email)
        _INBOX[email.id] = classified
        logger.info(
            f"Loaded {email.id} -> {classified.category.value} "
            f"(reply_required={classified.reply_required}, confidence={classified.confidence})"
        )


def _ensure_loaded() -> None:
    if not _INBOX:
        _load_mock_inbox()


def _send_via_gmail_stub(draft: DraftReply) -> bool:
    """
    Placeholder for the real Gmail send call, which lands in
    ingestion/gmail_client.py (final V1 module). Until then, approving
    a draft records the decision but never actually sends anything —
    this matches the PRD's "system never automatically sends emails in
    Version 1" principle, and keeps this router's contract stable: when
    gmail_client.py exists, only this function's body changes.
    """
    logger.info(f"[MOCK SEND] Would send email {draft.email_id} via Gmail (not yet wired).")
    return False


# ---------------------------------------------------------------------------
# GET /api/inbox
# ---------------------------------------------------------------------------
@router.get("/inbox")
def get_inbox():
    """
    Lightweight summary list for the /inbox dashboard page.
    Deliberately excludes body + draft (fetched via GET /email/{id})
    so this stays fast even once real Gmail data is wired in.
    """
    _ensure_loaded()

    summaries = []
    for classified in _INBOX.values():
        email = classified.email
        summaries.append({
            "id": email.id,
            "sender_name": email.sender.name,
            "sender_email": email.sender.email,
            "subject": email.subject,
            "timestamp": email.timestamp,
            "category": classified.category.value,
            "confidence": classified.confidence,
            "reply_required": classified.reply_required,
            "has_draft": email.id in _DRAFTS,
        })

    summaries.sort(key=lambda s: s["timestamp"], reverse=True)
    return summaries


# ---------------------------------------------------------------------------
# GET /api/email/{email_id}
# ---------------------------------------------------------------------------
@router.get("/email/{email_id}")
def get_email_detail(email_id: str):
    """
    Full detail view for /email/:id.

    If a reply is required and no draft exists yet, generates one
    synchronously via Ollama on this request. V1 has no background job
    queue, so the first person to open an email pays the generation
    latency — acceptable for a single-user local dashboard.
    """
    _ensure_loaded()

    classified = _INBOX.get(email_id)
    if classified is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")

    draft = _DRAFTS.get(email_id)

    if classified.reply_required and draft is None:
        try:
            draft = generate_reply(classified)
            _DRAFTS[email_id] = draft
        except OllamaClientError as e:
            logger.error(f"Draft generation failed for {email_id}: {e}")
            raise HTTPException(status_code=503, detail=str(e))

    return {
        "email": classified.email,
        "category": classified.category.value,
        "reply_required": classified.reply_required,
        "confidence": classified.confidence,
        "reason": classified.reason,
        "draft": draft,
    }


# ---------------------------------------------------------------------------
# POST /api/review/approve
# ---------------------------------------------------------------------------
@router.post("/review/approve", response_model=ApprovalResponse)
def approve_draft(request: ApprovalRequest):
    """
    Handles the user's decision on a draft: approve, edit, or reject.

    Every decision — including the full before/after text on edits — is
    appended to _FEEDBACK_LOG. Nothing consumes this yet, but this is
    exactly the record shape V2/V3's feedback pipeline (see PRD "Feedback
    Pipeline" section) needs, so we start capturing it from V1 onward
    rather than losing this data and back-filling later.
    """
    _ensure_loaded()

    if request.email_id not in _INBOX:
        raise HTTPException(status_code=404, detail=f"Email {request.email_id} not found")

    draft = _DRAFTS.get(request.email_id)
    if draft is None:
        raise HTTPException(
            status_code=400,
            detail=f"No draft exists for {request.email_id}. "
                   f"Call GET /api/email/{request.email_id} first to generate one."
        )

    sent = False
    original_body = draft.body

    if request.action == ApprovalAction.APPROVED:
        sent = _send_via_gmail_stub(draft)
        message = "Draft approved." if not sent else "Draft approved and sent."

    elif request.action == ApprovalAction.EDITED:
        draft.body = request.edited_body
        sent = _send_via_gmail_stub(draft)
        message = "Edited draft saved." if not sent else "Edited draft saved and sent."

    else:  # REJECTED
        message = "Draft rejected. No email will be sent."

    _FEEDBACK_LOG.append({
        "email_id": request.email_id,
        "action": request.action.value,
        "original_draft": original_body,
        "edited_body": request.edited_body,
        "logged_at": datetime.now(timezone.utc),
    })

    return ApprovalResponse(
        email_id=request.email_id,
        action=request.action,
        message=message,
        sent=sent,
    )