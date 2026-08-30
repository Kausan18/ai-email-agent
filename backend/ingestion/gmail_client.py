import base64
import html as html_lib
import re
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.models.email import CanonicalEmail, EmailSender
from backend.models.reply import DraftReply
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Gmail Client — V1 (final module)
# ---------------------------------------------------------------------------
# Responsibility: authenticate with Gmail, fetch recent messages and convert
# them into CanonicalEmail (same shape mock_data produces, so nothing
# downstream — classifier, prompt_builder, ollama_client — needs to change),
# and send an approved DraftReply back through Gmail.
#
# Every CanonicalEmail carries two body representations:
#   body       — plain text, always populated, what the classifier and
#                prompt_builder actually reason over
#   body_html  — raw HTML, Gmail only, None for mock data. Used ONLY for
#                faithful visual rendering in the dashboard (sandboxed
#                iframe) — never fed into classification or generation.
# ---------------------------------------------------------------------------


class GmailClientError(Exception):
    """Raised on auth failure, API errors, or malformed message parsing."""
    pass


def _get_credentials() -> Credentials:
    """
    Handles the OAuth flow. First run opens a browser for consent and
    writes token.json; subsequent runs reuse and silently refresh it.
    """
    creds: Credentials | None = None
    token_path = settings.GMAIL_TOKEN_PATH

    try:
        creds = Credentials.from_authorized_user_file(token_path, settings.GMAIL_SCOPES)
    except FileNotFoundError:
        pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not settings.GMAIL_CREDENTIALS_PATH:
                raise GmailClientError(
                    "GMAIL_CREDENTIALS_PATH is not set. Download credentials.json "
                    "from Google Cloud Console and set the path in .env."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GMAIL_CREDENTIALS_PATH, settings.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def _get_service():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------

def _extract_mime_part(payload: dict, mime_type: str) -> str | None:
    """Recursively finds and base64-decodes the first part matching mime_type."""
    body_data = payload.get("body", {}).get("data")
    if payload.get("mimeType") == mime_type and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    for sub_part in payload.get("parts", []):
        result = _extract_mime_part(sub_part, mime_type)
        if result:
            return result
    return None


def _clean_text(text: str) -> str:
    """
    Decodes entities and collapses whitespace. Applied to BOTH the plain-text
    and HTML-derived paths — some ESPs (e.g. Internshala) embed literal
    &nbsp;/&zwnj; entity codes directly inside the text/plain part itself
    as an anti-preview-snippet trick, so this isn't HTML-specific cleanup.
    """
    cleaned = html_lib.unescape(text)
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _html_to_text(raw_html: str) -> str:
    """Strips style/script blocks (including their content) and remaining tags."""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return _clean_text(cleaned)


def _decode_body(payload: dict) -> str:
    """
    Plain-text version of the email. This is what the classifier and
    prompt_builder reason over — never the raw HTML.
    """
    plain = _extract_mime_part(payload, "text/plain")
    if plain and len(plain.strip()) > 40:
        return _clean_text(plain)

    html_body = _extract_mime_part(payload, "text/html")
    if html_body:
        converted = _html_to_text(html_body)
        if converted:
            return converted

    return _clean_text(plain) if plain else "(no body content found)"


def _decode_html_body(payload: dict) -> str | None:
    """
    Raw HTML, kept ONLY for faithful visual rendering in the dashboard
    (sandboxed iframe). Never fed to the classifier or prompt builder.
    """
    return _extract_mime_part(payload, "text/html")


def _parse_sender(header_value: str) -> EmailSender:
    """
    Gmail's From header looks like 'Sarah Mitchell <sarah@techcorp.io>'
    or just 'sarah@techcorp.io'. Splits name from email accordingly.
    """
    match = re.match(r"^(.*?)\s*<(.+?)>$", header_value.strip())
    if match:
        name = match.group(1).strip().strip('"') or None
        email = match.group(2).strip()
        return EmailSender(name=name, email=email)
    return EmailSender(name=None, email=header_value.strip())


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _message_to_canonical(message: dict) -> CanonicalEmail:
    payload = message["payload"]
    headers = payload.get("headers", [])

    sender = _parse_sender(_get_header(headers, "From"))
    subject = _get_header(headers, "Subject") or "(no subject)"
    to_header = _get_header(headers, "To")
    recipients = [addr.strip() for addr in to_header.split(",")] if to_header else []

    internal_ts_ms = int(message.get("internalDate", "0"))
    timestamp = datetime.fromtimestamp(internal_ts_ms / 1000, tz=timezone.utc)

    body = _decode_body(payload)
    body_html = _decode_html_body(payload)

    return CanonicalEmail(
        id=message["id"],
        thread_id=message.get("threadId"),
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=body,
        body_html=body_html,
        timestamp=timestamp,
        is_reply=subject.lower().startswith("re:"),
        raw_headers={h["name"]: h["value"] for h in headers},
    )


def fetch_recent_emails(max_results: int | None = None) -> list[CanonicalEmail]:
    """
    Fetches the most recent inbox messages and converts each to a
    CanonicalEmail. This is the Gmail equivalent of reading
    mock_data/emails.json — same output shape (plus body_html), so
    approval_router's inbox-loading logic needs no changes.
    """
    max_results = max_results or settings.GMAIL_MAX_RESULTS

    try:
        service = _get_service()
        results = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=max_results
        ).execute()
        message_refs = results.get("messages", [])

        emails = []
        for ref in message_refs:
            full_message = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()
            emails.append(_message_to_canonical(full_message))

        logger.info(f"Fetched {len(emails)} emails from Gmail")
        return emails

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        raise GmailClientError(f"Gmail API request failed: {e}") from e


def send_reply(draft: DraftReply, to_email: str, thread_id: str | None = None) -> bool:
    """
    Sends an approved/edited draft as a reply via Gmail.
    """
    try:
        service = _get_service()

        message_text = (
            f"To: {to_email}\r\n"
            f"Subject: {draft.subject}\r\n\r\n"
            f"{draft.body}"
        )
        raw = base64.urlsafe_b64encode(message_text.encode("utf-8")).decode("utf-8")

        body = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id

        service.users().messages().send(userId="me", body=body).execute()
        logger.info(f"Sent reply for {draft.email_id} to {to_email}")
        return True

    except HttpError as e:
        logger.error(f"Failed to send email via Gmail: {e}")
        return False