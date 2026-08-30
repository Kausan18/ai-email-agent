import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.config import settings, MOCK_DATA_PATH
from backend.models.email import CanonicalEmail, ClassifiedEmail
from backend.models.reply import DraftReply, ApprovalRequest, ApprovalResponse, ApprovalAction
from backend.classification.classifier import classify_email
from backend.inference.ollama_client import generate_reply, OllamaClientError
from backend.ingestion.gmail_client import fetch_recent_emails, send_reply, GmailClientError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["review"])


# ---------------------------------------------------------------------------
# In-memory stores — V1 only.
# ---------------------------------------------------------------------------
_INBOX: dict[str, ClassifiedEmail] = {}
_DRAFTS: dict[str, DraftReply] = {}
_FEEDBACK_LOG: list[dict] = []


def _load_mock_inbox() -> None:
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
    if _INBOX:
        return

    if settings.USE_GMAIL:
        try:
            emails = fetch_recent_emails()
            for email in emails:
                _INBOX[email.id] = classify_email(email)
        except GmailClientError as e:
            logger.error(f"Gmail fetch failed, falling back to mock data: {e}")
            _load_mock_inbox()
    else:
        _load_mock_inbox()


def _send_via_gmail_stub(draft: DraftReply) -> bool:
    if not settings.USE_GMAIL:
        logger.info(f"[MOCK SEND] Would send email {draft.email_id} via Gmail (USE_GMAIL=False).")
        return False

    classified = _INBOX.get(draft.email_id)
    if classified is None:
        logger.error(f"Cannot send {draft.email_id}: not found in inbox cache.")
        return False

    return send_reply(draft, to_email=classified.email.sender.email, thread_id=classified.email.thread_id)


# ---------------------------------------------------------------------------
# GET /api/inbox
# ---------------------------------------------------------------------------
@router.get("/inbox")
def get_inbox(
    needs_reply: bool | None = Query(
        None, description="Filter by reply_required. Omit to return everything."
    )
):
    """
    Lightweight summary list. `needs_reply=true` returns only emails the
    agent decided require a reply (drafts generated or pending) — the
    dashboard's main Inbox view. `needs_reply=false` returns everything
    filed automatically (newsletters, acknowledgments, promotions per
    EC-1/EC-2) — the "Filed" sidebar view. Omitting the param returns both.
    """
    _ensure_loaded()

    summaries = []
    for classified in _INBOX.values():
        if needs_reply is not None and classified.reply_required != needs_reply:
            continue

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