"""
memory_writer.py
----------------
Decides what to write to Supabase after entity extraction, and calls
the appropriate db.py function.

Public API
----------
write_entity(
    entity: EntityResult,
    category: str,
    thread_id: str,
    sender_email: str,
    sender_name: str,
) -> MemoryWriteResult

Decision logic per entity type
-------------------------------
RecruiterEntity   → upsert contact → upsert company → upsert recruiter
                    (application_id stays None for EC-8 cold outreach)

ApplicationEntity → upsert company → check for existing application
                    (same company + role) → insert_new or update_existing
                    If company is UNKNOWN and no prior record → unverified

ConferenceEntity  → check conference_submissions by name
                    If none found → unverified (EC-19)
                    If found → update status

MeetingEntity     → check meetings by thread_id
                    If none → insert_new
                    If found → update_existing (EC-9 / EC-26)

GeneralEntity     → insert email_note (catch-all)

NO_EXTRACT cats   → skip (NEWSLETTER / PROMOTION — writer never called)

Edge cases handled
------------------
EC-8   Recruiter cold outreach  → nullable application_id FK
EC-9   Thread continuation      → update meeting, not insert
EC-19  Unknown conference       → unverified_events, not conference_submissions
EC-20  Unknown internship       → unverified_events, not applications
EC-25  Duplicate prevention     → check before insert for all entity types
EC-26  Status update            → update_application_status / update_meeting_status
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.extraction.schemas import (
    ApplicationEntity,
    ConferenceEntity,
    EntityResult,
    GeneralEntity,
    MeetingEntity,
    RecruiterEntity,
)
from backend.memory.db import (
    get_applications_by_company,
    get_conference_by_name,
    get_contact_by_email,
    get_notes_by_thread,
    get_recruiter_by_contact,
    insert_application,
    insert_conference_submission,
    insert_email_note,
    insert_meeting,
    insert_unverified_event,
    update_application_status,
    update_conference_status,
    update_meeting_status,
    upsert_company,
    upsert_contact,
    upsert_recruiter,
)
from backend.memory.entity_resolver import ResolvedCompany, resolve_company

# Minimum extraction confidence to write anything at all.
# Below this the LLM output is too unreliable to persist.
MIN_WRITE_CONFIDENCE = 0.30

# Categories the writer must never be called for, but we guard anyway.
NO_WRITE_CATEGORIES = {"NEWSLETTER", "PROMOTION"}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MemoryWriteResult:
    """
    Returned by write_entity() for every call.

    Fields
    ------
    action          What the writer did:
                      "insert_new"       — new record created
                      "update_existing"  — existing record updated
                      "route_to_unverified" — sent to unverified_events queue
                      "skip"             — confidence too low or no-write category
    entity_type     String name of the Pydantic entity class used.
    record_id       UUID of the primary affected row, or None for skip.
    confidence      extraction_confidence passed through from the entity.
    resolved_company  ResolvedCompany from entity_resolver, or None.
    notes           Human-readable explanation (surfaced in planner + dashboard).
    extra           Any additional IDs or metadata the caller might need.
    """
    action: str
    entity_type: str
    record_id: str | None
    confidence: float
    resolved_company: ResolvedCompany | None
    notes: str
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(raw_name: str | None) -> ResolvedCompany | None:
    if not raw_name:
        return None
    return resolve_company(raw_name)


def _ensure_company(resolved: ResolvedCompany | None, raw_name: str | None) -> str | None:
    """
    Given a resolved company result, upsert the company row if needed and
    return the canonical company UUID.

    - exact_alias / exact_name / fuzzy_high → use existing canonical_id
    - fuzzy_low / no_match → create a new company record, return its id
    - None raw_name → return None
    """
    if raw_name is None:
        return None

    if resolved and resolved.canonical_id and resolved.resolution in (
        "exact_alias", "exact_name", "fuzzy_high"
    ):
        return resolved.canonical_id

    # No confident match — create a new canonical company record.
    result = upsert_company({"name": raw_name})
    return result.get("id") if result else None


# ---------------------------------------------------------------------------
# Per-entity-type write handlers
# ---------------------------------------------------------------------------

def _write_recruiter(
    entity: RecruiterEntity,
    thread_id: str,
    sender_email: str,
    sender_name: str,
    resolved: ResolvedCompany | None,
) -> MemoryWriteResult:
    """
    EC-8: application_id is nullable — cold outreach before any application.
    Deduplication: contact identified by email; recruiter by contact_id.
    """
    company_id = _ensure_company(resolved, entity.company)

    # Upsert contact row
    contact_row = upsert_contact({
        "name": entity.recruiter_name or sender_name,
        "email": entity.recruiter_email or sender_email,
        "company_id": company_id,
        "relationship_type": "recruiter",
    })
    contact_id = contact_row.get("id") if contact_row else None

    # Check if recruiter record already exists
    existing_recruiter = get_recruiter_by_contact(contact_id) if contact_id else None
    action = "update_existing" if existing_recruiter else "insert_new"

    recruiter_row = upsert_recruiter({
    "contact_id": contact_id,
    "company_id": company_id,
    "thread_id": thread_id,
    "application_id": None,
})
    record_id = recruiter_row.get("id") if recruiter_row else None

    notes = (
        f"{'Updated' if action == 'update_existing' else 'Created'} recruiter record "
        f"for {entity.recruiter_name or sender_name} at "
        f"{entity.company or 'unknown company'}. "
        f"application_id=None (cold outreach — EC-8)."
    )
    if resolved:
        notes += f" Company resolved via '{resolved.resolution}' (confidence={resolved.confidence})."

    return MemoryWriteResult(
        action=action,
        entity_type="RecruiterEntity",
        record_id=record_id,
        confidence=entity.extraction_confidence,
        resolved_company=resolved,
        notes=notes,
        extra={"contact_id": contact_id, "company_id": company_id},
    )


def _write_application(
    entity: ApplicationEntity,
    thread_id: str,
    sender_email: str,
    resolved: ResolvedCompany | None,
) -> MemoryWriteResult:
    """
    EC-20: If no prior application found and company unknown → unverified_events.
    EC-25/EC-26: If application for same (company, role) exists → update status.
    """
    company_id = _ensure_company(resolved, entity.company)

    # Check for existing application at same company + role
    existing_apps = get_applications_by_company(company_id) if company_id else []
    existing = next(
        (a for a in existing_apps if a.get("role", "").lower() == (entity.role or "").lower()),
        None,
    )

    # EC-20: Unverified path — acknowledgment for something not in our records
    # Triggered when: no company match AND no existing application
    if not company_id and not existing:
        unverified_row = insert_unverified_event({
            "email_id": thread_id,
            "event_type": "application",
            "raw_data": {
                "company": entity.company,
                "role": entity.role,
                "platform": entity.platform,
                "application_id": entity.application_id,
                "application_date": entity.application_date,
                "sender_email": sender_email,
                "thread_id": thread_id,
            },
            "reason": "No prior application record found for this company/role (EC-20).",
        })
        return MemoryWriteResult(
            action="route_to_unverified",
            entity_type="ApplicationEntity",
            record_id=unverified_row.get("id") if unverified_row else None,
            confidence=entity.extraction_confidence,
            resolved_company=resolved,
            notes=(
                f"Application acknowledgment for '{entity.company} — {entity.role}' "
                f"has no matching prior record. Routed to unverified_events (EC-20)."
            ),
        )

    # EC-26: Existing application → update status
    if existing:
        new_status = entity.status or "applied"
        update_application_status(existing["id"], new_status)
        return MemoryWriteResult(
            action="update_existing",
            entity_type="ApplicationEntity",
            record_id=existing["id"],
            confidence=entity.extraction_confidence,
            resolved_company=resolved,
            notes=(
                f"Updated existing application for '{entity.company} — {entity.role}' "
                f"to status='{new_status}' (EC-26)."
            ),
            extra={"company_id": company_id},
        )

    # New application → insert
    app_row = insert_application({
        "company_id": company_id,
        "role": entity.role,
        "platform": entity.platform,
        "application_id": entity.application_id,
        "application_date": entity.application_date,
        "status": entity.status or "applied",
    })
    return MemoryWriteResult(
        action="insert_new",
        entity_type="ApplicationEntity",
        record_id=app_row.get("id") if app_row else None,
        confidence=entity.extraction_confidence,
        resolved_company=resolved,
        notes=(
            f"Inserted new application: '{entity.company} — {entity.role}' "
            f"via {entity.platform or 'unknown platform'}."
        ),
        extra={"company_id": company_id},
    )


def _write_conference(
    entity: ConferenceEntity,
    thread_id: str,
    sender_email: str,
) -> MemoryWriteResult:
    """
    EC-19: If no prior conference submission found → unverified_events.
    EC-26: If found → update status.
    """
    existing = get_conference_by_name(entity.conference_name) if entity.conference_name else None

    # EC-19: No prior submission — don't trust the acknowledgment
    if not existing:
        unverified_row = insert_unverified_event({
            "email_id": thread_id,
            "event_type": "conference",
            "raw_data": {
                "conference_name": entity.conference_name,
                "paper_title": entity.paper_title,
                "submission_id": entity.submission_id,
                "status": entity.status,
                "camera_ready_deadline": entity.camera_ready_deadline,
                "presentation_date": entity.presentation_date,
                "sender_email": sender_email,
                "thread_id": thread_id,
            },
            "reason": "No prior conference submission found for this conference (EC-19).",
        })
        return MemoryWriteResult(
            action="route_to_unverified",
            entity_type="ConferenceEntity",
            record_id=unverified_row.get("id") if unverified_row else None,
            confidence=entity.extraction_confidence,
            resolved_company=None,
            notes=(
                f"Conference acknowledgment for '{entity.conference_name}' "
                f"has no matching prior submission. Routed to unverified_events (EC-19)."
            ),
        )

    # Found existing submission → update status
    new_status = entity.status or existing.get("status", "submitted")
    update_conference_status(existing["id"], new_status)
    return MemoryWriteResult(
        action="update_existing",
        entity_type="ConferenceEntity",
        record_id=existing["id"],
        confidence=entity.extraction_confidence,
        resolved_company=None,
        notes=(
            f"Updated conference submission '{entity.conference_name}' "
            f"to status='{new_status}' (EC-26)."
        ),
    )


def _write_meeting(
    entity: MeetingEntity,
    thread_id: str,
    sender_email: str,
) -> MemoryWriteResult:
    """
    EC-9 / EC-26: If a meeting already exists for this thread_id → update, not insert.
    """
    from backend.memory.db import get_meeting_by_thread   # local import to avoid circular

    existing = get_meeting_by_thread(thread_id) if thread_id else None

    if existing:
        update_meeting_status(existing["id"], "rescheduled")
        return MemoryWriteResult(
            action="update_existing",
            entity_type="MeetingEntity",
            record_id=existing["id"],
            confidence=entity.extraction_confidence,
            resolved_company=None,
            notes=(
                f"Updated existing meeting on thread '{thread_id}' "
                f"— thread continuation (EC-9 / EC-26)."
            ),
        )

    meeting_row = insert_meeting({
    "title": entity.title,
    "scheduled_time": entity.scheduled_time,
    "participants": entity.participants or [],
    "thread_id": thread_id,
    "status": "scheduled",
})
    return MemoryWriteResult(
        action="insert_new",
        entity_type="MeetingEntity",
        record_id=meeting_row.get("id") if meeting_row else None,
        confidence=entity.extraction_confidence,
        resolved_company=None,
        notes=f"Inserted new meeting: '{entity.title}'.",
    )


def _write_general(
    entity: GeneralEntity,
    thread_id: str,
    sender_email: str,
    sender_name: str,
) -> MemoryWriteResult:
    """
    Catch-all: insert an email_note.
    contact_id is looked up by sender_email; nullable for unknown senders (EC-18).
    Deduplication: skip if we already have a note for this thread.
    """
    # Check for existing note on same thread (EC-25 for general emails)
    existing_notes = get_notes_by_thread(thread_id) if thread_id else []
    if existing_notes:
        return MemoryWriteResult(
            action="update_existing",
            entity_type="GeneralEntity",
            record_id=existing_notes[0].get("id"),
            confidence=entity.extraction_confidence,
            resolved_company=None,
            notes=f"Thread '{thread_id}' already has an email_note — skipping duplicate (EC-25).",
        )

    # Look up contact (nullable — EC-18)
    contact_row = get_contact_by_email(sender_email) if sender_email else None
    contact_id = contact_row.get("id") if contact_row else None

    note_row = insert_email_note({
    "contact_id": contact_id,
    "thread_id": thread_id,
    "category": "general",
    "summary": entity.topic or f"Email from {sender_name or sender_email}",
    "raw_context": entity.notes,
})
    return MemoryWriteResult(
        action="insert_new",
        entity_type="GeneralEntity",
        record_id=note_row.get("id") if note_row else None,
        confidence=entity.extraction_confidence,
        resolved_company=None,
        notes=(
            f"Inserted email_note for sender '{sender_email}'. "
            f"contact_id={'None — unknown sender (EC-18)' if not contact_id else contact_id}."
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_entity(
    entity: EntityResult,
    category: str,
    thread_id: str,
    sender_email: str,
    sender_name: str = "",
) -> MemoryWriteResult:
    """
    Persist an extracted entity to Supabase.

    Parameters
    ----------
    entity        Output of extract_entities() — a Pydantic entity instance.
    category      Email category string (RECRUITER, INTERNSHIP, MEETING, etc.)
    thread_id     Gmail thread ID — used for deduplication and updates.
    sender_email  From: address of the original email.
    sender_name   Display name of the sender (optional, used as fallback).

    Returns
    -------
    MemoryWriteResult
        Always returned, never raises. On unexpected errors the action
        will be "skip" with an explanatory notes field.
    """
    # Guard: never write newsletters / promotions
    if category.upper() in NO_WRITE_CATEGORIES:
        return MemoryWriteResult(
            action="skip",
            entity_type=type(entity).__name__,
            record_id=None,
            confidence=getattr(entity, "extraction_confidence", 0.0),
            resolved_company=None,
            notes=f"Category '{category}' is a no-write category. Writer not called.",
        )

    # Guard: confidence floor
    confidence = getattr(entity, "extraction_confidence", 0.0)
    if confidence < MIN_WRITE_CONFIDENCE:
        return MemoryWriteResult(
            action="skip",
            entity_type=type(entity).__name__,
            record_id=None,
            confidence=confidence,
            resolved_company=None,
            notes=(
                f"extraction_confidence={confidence} is below MIN_WRITE_CONFIDENCE="
                f"{MIN_WRITE_CONFIDENCE}. Skipping write to avoid persisting unreliable data."
            ),
        )

    try:
        if isinstance(entity, RecruiterEntity):
            resolved = _resolve(entity.company)
            return _write_recruiter(entity, thread_id, sender_email, sender_name, resolved)

        if isinstance(entity, ApplicationEntity):
            resolved = _resolve(entity.company)
            return _write_application(entity, thread_id, sender_email, resolved)

        if isinstance(entity, ConferenceEntity):
            return _write_conference(entity, thread_id, sender_email)

        if isinstance(entity, MeetingEntity):
            return _write_meeting(entity, thread_id, sender_email)

        if isinstance(entity, GeneralEntity):
            return _write_general(entity, thread_id, sender_email, sender_name)

        # Unknown entity type — shouldn't happen but safe to handle
        return MemoryWriteResult(
            action="skip",
            entity_type=type(entity).__name__,
            record_id=None,
            confidence=confidence,
            resolved_company=None,
            notes=f"Unrecognised entity type '{type(entity).__name__}'. No write performed.",
        )

    except Exception as exc:
        import traceback; traceback.print_exc() 
        return MemoryWriteResult(
            action="skip",
            entity_type=type(entity).__name__,
            record_id=None,
            confidence=confidence,
            resolved_company=None,
            notes=f"Unexpected error during write: {exc}",
        )