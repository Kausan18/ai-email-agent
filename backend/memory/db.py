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

def upsert_company(name: str, domain: str | None = None) -> dict:
    """Insert company if not exists, return its record."""
    client = _client()
    existing = (
        client.table("companies")
        .select("*")
        .eq("name", name)
        .execute()
    )
    if existing.data:
        return existing.data[0]
    result = client.table("companies").insert({"name": name, "domain": domain}).execute()
    return result.data[0]


def get_company_by_name(name: str) -> dict | None:
    result = _client().table("companies").select("*").eq("name", name).execute()
    return result.data[0] if result.data else None


# ── Contacts ───────────────────────────────────────────────────────────────

def upsert_contact(
    email: str,
    name: str | None = None,
    company_id: str | None = None,
    relationship_type: str = "unknown",   # ← add this
) -> dict:
    client = _client()
    existing = client.table("contacts").select("*").eq("email", email).execute()
    if existing.data:
        return existing.data[0]
    result = client.table("contacts").insert({
        "email": email,
        "name": name,
        "company_id": company_id,
        "relationship_type": relationship_type,   # ← and this
    }).execute()
    return result.data[0]


def get_contact_by_email(email: str) -> dict | None:
    result = _client().table("contacts").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None


# ── Recruiters ─────────────────────────────────────────────────────────────

def upsert_recruiter(contact_id: str, company_id: str | None, thread_id: str | None) -> dict:
    client = _client()
    existing = client.table("recruiters").select("*").eq("contact_id", contact_id).execute()
    if existing.data:
        return existing.data[0]
    result = client.table("recruiters").insert({
        "contact_id": contact_id,
        "company_id": company_id,
        "thread_id": thread_id,
    }).execute()
    return result.data[0]


def get_recruiter_by_contact(contact_id: str) -> dict | None:
    result = _client().table("recruiters").select("*").eq("contact_id", contact_id).execute()
    return result.data[0] if result.data else None


# ── Applications ───────────────────────────────────────────────────────────

def insert_application(
    company_id: str,
    role: str,
    status: str = "applied",
    platform: str | None = None,
    application_id: str | None = None,
    application_date: str | None = None,
) -> dict:
    result = _client().table("applications").insert({
        "company_id": company_id,
        "role": role,
        "status": status,
        "platform": platform,
        "application_id": application_id,
        "application_date": application_date,
    }).execute()
    return result.data[0]


def update_application_status(application_id_pk: str, new_status: str) -> dict:
    result = (
        _client()
        .table("applications")
        .update({"status": new_status, "updated_at": "NOW()"})
        .eq("id", application_id_pk)
        .execute()
    )
    return result.data[0]


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

def insert_meeting(
    title: str | None,
    scheduled_time: str | None,
    participants: list[str],
    thread_id: str | None,
) -> dict:
    result = _client().table("meetings").insert({
        "title": title,
        "scheduled_time": scheduled_time,
        "participants": participants,
        "thread_id": thread_id,
    }).execute()
    return result.data[0]


def update_meeting_status(meeting_id: str, new_status: str) -> dict:
    result = (
        _client()
        .table("meetings")
        .update({"status": new_status, "updated_at": "NOW()"})
        .eq("id", meeting_id)
        .execute()
    )
    return result.data[0]


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

def insert_email_note(
    contact_id: str | None,
    thread_id: str | None,
    category: str,
    summary: str,
    raw_context: str | None = None,
    email_date: str | None = None,
) -> dict:
    result = _client().table("email_notes").insert({
        "contact_id": contact_id,
        "thread_id": thread_id,
        "category": category,
        "summary": summary,
        "raw_context": raw_context,
        "email_date": email_date,
    }).execute()
    return result.data[0]


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

def insert_conference_submission(
    conference_name: str,
    paper_title: str | None = None,
    submission_id: str | None = None,
    status: str = "submitted",
    submission_date: str | None = None,
) -> dict:
    result = _client().table("conference_submissions").insert({
        "conference_name": conference_name,
        "paper_title": paper_title,
        "submission_id": submission_id,
        "status": status,
        "submission_date": submission_date,
    }).execute()
    return result.data[0]


def update_conference_status(submission_id_pk: str, new_status: str) -> dict:
    result = (
        _client()
        .table("conference_submissions")
        .update({"status": new_status, "updated_at": "NOW()"})
        .eq("id", submission_id_pk)
        .execute()
    )
    return result.data[0]


def get_conference_by_name(conference_name: str) -> dict | None:
    result = (
        _client()
        .table("conference_submissions")
        .select("*")
        .eq("conference_name", conference_name)
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

def insert_unverified_event(
    email_id: str,
    event_type: str,
    raw_data: dict,
    reason: str | None = None,
) -> dict:
    result = _client().table("unverified_events").insert({
        "email_id": email_id,
        "event_type": event_type,
        "raw_data": raw_data,
        "reason": reason,
    }).execute()
    return result.data[0]


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