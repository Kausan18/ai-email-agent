"""
backend/memory/db.py

CRUD layer for all Supabase structured memory tables.
All functions return dicts or lists of dicts — no ORM objects.
"""

from supabase import create_client, Client
from backend.config import settings

def _client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# ── Companies ──────────────────────────────────────────────────────────────

def upsert_company(data: dict) -> dict | None:
    client = _client()
    name = data.get("name")
    if name:
        existing = client.table("companies").select("*").eq("name", name).execute()
        if existing.data:
            return existing.data[0]
    clean = {k: v for k, v in data.items() if v is not None}
    result = client.table("companies").insert(clean).execute()
    return result.data[0] if result.data else None


def get_company_by_name(name: str) -> dict | None:
    result = _client().table("companies").select("*").eq("name", name).execute()
    return result.data[0] if result.data else None


# ── Contacts ───────────────────────────────────────────────────────────────

def upsert_contact(data: dict) -> dict | None:
    client = _client()
    email = data.get("email")
    if email:
        existing = client.table("contacts").select("*").eq("email", email).execute()
        if existing.data:
            return existing.data[0]
    clean = {k: v for k, v in data.items() if v is not None}
    result = client.table("contacts").insert(clean).execute()
    return result.data[0] if result.data else None

def get_contact_by_email(email: str) -> dict | None:
    result = _client().table("contacts").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None


# ── Recruiters ─────────────────────────────────────────────────────────────

def upsert_recruiter(data: dict) -> dict | None:
    """
    Insert a new recruiter row or return the existing one for this contact.
    Strips None values before sending to Postgres to avoid UUID cast errors.
    """
    client = _client()

    # Deduplication check — one recruiter record per contact
    contact_id = data.get("contact_id")
    if contact_id:
        existing = (
            client.table("recruiters")
            .select("*")
            .eq("contact_id", contact_id)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    # Strip None values so Postgres never receives "None" as a UUID string
    clean = {k: v for k, v in data.items() if v is not None}
    result = client.table("recruiters").insert(clean).execute()
    return result.data[0] if result.data else None


def get_recruiter_by_contact(contact_id: str) -> dict | None:
    result = _client().table("recruiters").select("*").eq("contact_id", contact_id).execute()
    return result.data[0] if result.data else None


# ── Applications ───────────────────────────────────────────────────────────

def insert_application(data: dict) -> dict | None:
    clean = {k: v for k, v in data.items() if v is not None}
    result = _client().table("applications").insert(clean).execute()
    return result.data[0] if result.data else None


def update_application_status(application_id_pk: str, new_status: str) -> dict | None:
    result = (
        _client()
        .table("applications")
        .update({"status": new_status})
        .eq("id", application_id_pk)
        .execute()
    )
    return result.data[0] if result.data else None


def get_applications_by_company(company_id: str) -> list[dict]:
    result = (
        _client()
        .table("applications")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )
    return result.data


def get_active_applications() -> list[dict]:
    result = (
        _client()
        .table("applications")
        .select("*")
        .not_.in_("status", ["rejected", "withdrawn", "expired"])
        .execute()
    )
    return result.data


# ── Meetings ───────────────────────────────────────────────────────────────

def insert_meeting(data: dict) -> dict | None:
    clean = {k: v for k, v in data.items() if v is not None}
    result = _client().table("meetings").insert(clean).execute()
    return result.data[0] if result.data else None


def update_meeting_status(meeting_id: str, new_status: str) -> dict | None:
    result = (
        _client()
        .table("meetings")
        .update({"status": new_status})
        .eq("id", meeting_id)
        .execute()
    )
    return result.data[0] if result.data else None



# ── Entity Aliases ─────────────────────────────────────────────────────────

def insert_alias(canonical_id: str, alias: str, entity_type: str, confidence: float = 1.0) -> dict:
    result = _client().table("entity_aliases").insert({
        "canonical_id": canonical_id,
        "alias": alias,
        "entity_type": entity_type,
        "confidence": confidence,
    }).execute()
    return result.data[0]


def find_alias(alias: str, entity_type: str) -> dict | None:
    result = (
        _client()
        .table("entity_aliases")
        .select("*")
        .eq("alias", alias)
        .eq("entity_type", entity_type)
        .execute()
    )
    return result.data[0] if result.data else None


# ── Planner Logs ───────────────────────────────────────────────────────────

def log_planner_decision(email_id: str, decisions: dict) -> dict:
    result = _client().table("planner_logs").insert({
        "email_id": email_id,
        "decisions": decisions,
    }).execute()
    return result.data[0]


def get_planner_log(email_id: str) -> dict | None:
    result = (
        _client()
        .table("planner_logs")
        .select("*")
        .eq("email_id", email_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None

# ── Email Notes (unstructured context) ────────────────────────────────────

def insert_email_note(data: dict) -> dict | None:
    clean = {k: v for k, v in data.items() if v is not None}
    result = _client().table("email_notes").insert(clean).execute()
    return result.data[0] if result.data else None


def get_notes_by_contact(contact_id: str) -> list[dict]:
    result = (
        _client()
        .table("email_notes")
        .select("*")
        .eq("contact_id", contact_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_notes_by_thread(thread_id: str) -> list[dict]:
    result = (
        _client()
        .table("email_notes")
        .select("*")
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data

# ── Conference Submissions ─────────────────────────────────────────────────

def insert_conference_submission(data: dict) -> dict | None:
    client = _client()
    submission_id = data.get("submission_id")
    if submission_id:
        existing = (
            client.table("conference_submissions")
            .select("*")
            .eq("submission_id", submission_id)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    conference_name = data.get("conference_name")
    if conference_name:
        existing = (
            client.table("conference_submissions")
            .select("*")
            .eq("conference_name", conference_name)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    clean = {k: v for k, v in data.items() if v is not None}
    result = client.table("conference_submissions").insert(clean).execute()
    return result.data[0] if result.data else None


def update_conference_status(submission_id_pk: str, new_status: str) -> dict | None:
    result = (
        _client()
        .table("conference_submissions")
        .update({"status": new_status})
        .eq("id", submission_id_pk)
        .execute()
    )
    return result.data[0] if result.data else None

def get_conference_by_name(conference_name: str) -> dict | None:
    result = (
        _client()
        .table("conference_submissions")
        .select("*")
        .eq("conference_name", conference_name)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_active_conference_submissions() -> list[dict]:
    result = (
        _client()
        .table("conference_submissions")
        .select("*")
        .not_.in_("status", ["rejected", "withdrawn"])
        .execute()
    )
    return result.data


# ── Unverified Events ──────────────────────────────────────────────────────

def insert_unverified_event(data: dict) -> dict | None:
    clean = {k: v for k, v in data.items() if v is not None}
    result = _client().table("unverified_events").insert(clean).execute()
    return result.data[0] if result.data else None


def get_unverified_events(event_type: str | None = None) -> list[dict]:
    client = _client()
    query = client.table("unverified_events").select("*")
    if event_type:
        query = query.eq("event_type", event_type)
    result = query.order("created_at", desc=True).execute()
    return result.data


def resolve_unverified_event(event_id: str) -> None:
    """Remove an unverified event once the user has confirmed or dismissed it."""
    _client().table("unverified_events").delete().eq("id", event_id).execute()


# ── Flagged Emails ─────────────────────────────────────────────────────────

def flag_email(
    email_id: str,
    reason: str,
    sender: str | None = None,
) -> dict:
    result = _client().table("flagged_emails").insert({
        "email_id": email_id,
        "reason": reason,
        "sender": sender,
    }).execute()
    return result.data[0]


def get_flagged_emails(reviewed: bool = False) -> list[dict]:
    result = (
        _client()
        .table("flagged_emails")
        .select("*")
        .eq("reviewed", reviewed)
        .order("flagged_at", desc=True)
        .execute()
    )
    return result.data


def mark_flag_reviewed(flag_id: str) -> dict:
    result = (
        _client()
        .table("flagged_emails")
        .update({"reviewed": True})
        .eq("id", flag_id)
        .execute()
    )
    return result.data[0]

def get_meeting_by_thread(thread_id: str) -> dict | None:
    response = (
        _client()
        .table("meetings")
        .select("*")
        .eq("thread_id", thread_id)
        .maybe_single()
        .execute()
    )
    return response.data