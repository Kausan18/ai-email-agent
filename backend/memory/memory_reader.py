"""
memory_reader.py
----------------
Retrieves all stored context relevant to an incoming email.
Called by the Planner (Phase 4) before deciding reply strategy.

Public API
----------
get_context(
    sender_email: str,
    company_name: str | None,
    thread_id: str | None,
) -> RetrievedContext

retrieval_confidence heuristic
-------------------------------
1.0  contact found + at least one application or meeting
0.8  contact found + conference submission
0.6  contact found but no applications / meetings / conferences
0.4  no contact, but company match found (fuzzy or exact)
0.2  no contact, no company, but email_notes exist for thread
0.0  nothing found anywhere

EC coverage
-----------
EC-10 / EC-11  Entity alias resolution feeds company_id lookup
EC-12          Conference follow-up: conference_submissions returned in context
EC-13          Long-term memory: all historical records returned, not just recent
EC-27          Inactive applications included but flagged as inactive
EC-28          Multiple applications to same company all returned as list
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.memory.db import (
    get_active_applications,
    get_applications_by_company,
    get_contact_by_email,
    get_notes_by_contact,
    get_notes_by_thread,
    get_recruiter_by_contact,
    get_unverified_events,
    get_active_conference_submissions,
    get_conference_by_name,
)
from backend.memory.entity_resolver import resolve_company


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class RetrievedContext:
    """
    All context retrieved for a single incoming email.
    Passed directly to the Planner and Prompt Builder.

    Fields
    ------
    contact             Row from contacts table, or None (EC-18 unknown sender).
    recruiter           Row from recruiters table, or None.
    applications        All application rows for this company (EC-28 multi-app).
    active_applications Subset of applications with active status.
    meetings            Meeting rows linked to this thread, or all for contact.
    conference_submissions  All conference rows (EC-12 follow-up support).
    email_notes         Free-text notes for this contact or thread.
    unverified_events   Pending items in /uncertain queue for this sender.
    retrieval_confidence  0.0 – 1.0 heuristic (see module docstring).
    retrieval_summary   Human-readable summary for planner reasoning field.
    company_id          Resolved canonical company UUID, or None.
    """
    contact: dict | None = None
    recruiter: dict | None = None
    applications: list[dict] = field(default_factory=list)
    active_applications: list[dict] = field(default_factory=list)
    meetings: list[dict] = field(default_factory=list)
    conference_submissions: list[dict] = field(default_factory=list)
    email_notes: list[dict] = field(default_factory=list)
    unverified_events: list[dict] = field(default_factory=list)
    retrieval_confidence: float = 0.0
    retrieval_summary: str = ""
    company_id: str | None = None


# ---------------------------------------------------------------------------
# Confidence heuristic
# ---------------------------------------------------------------------------

def _score_confidence(ctx: RetrievedContext) -> float:
    """
    Simple additive heuristic. See module docstring for scale.
    """
    if ctx.contact and (ctx.active_applications or ctx.meetings):
        return 1.0
    if ctx.contact and ctx.conference_submissions:
        return 0.8
    if ctx.contact:
        return 0.6
    if ctx.company_id and (ctx.applications or ctx.conference_submissions):
        return 0.4
    if ctx.email_notes:
        return 0.2
    return 0.0


def _build_summary(ctx: RetrievedContext) -> str:
    parts = []
    if ctx.contact:
        parts.append(f"Contact: {ctx.contact.get('name', 'unknown')} ({ctx.contact.get('email', '')})")
    if ctx.recruiter:
        parts.append("Recruiter record found.")
    if ctx.applications:
        roles = [a.get("role", "unknown role") for a in ctx.applications]
        parts.append(f"Applications: {', '.join(roles)}")
    if ctx.active_applications:
        parts.append(f"Active applications: {len(ctx.active_applications)}")
    if ctx.meetings:
        parts.append(f"Meetings on thread: {len(ctx.meetings)}")
    if ctx.conference_submissions:
        names = [c.get("conference_name", "unknown") for c in ctx.conference_submissions]
        parts.append(f"Conference submissions: {', '.join(names)}")
    if ctx.unverified_events:
        parts.append(f"Unverified events pending review: {len(ctx.unverified_events)}")
    if ctx.email_notes:
        parts.append(f"Prior email notes: {len(ctx.email_notes)}")
    if not parts:
        return "No prior context found for this sender or company."
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_context(
    sender_email: str,
    company_name: str | None = None,
    thread_id: str | None = None,
) -> RetrievedContext:
    """
    Retrieve all stored context relevant to an incoming email.

    Parameters
    ----------
    sender_email    From: address of the incoming email.
    company_name    Raw company name from entity extraction (may be fuzzy).
                    If None, company-level lookups are skipped.
    thread_id       Gmail thread ID. Used to fetch thread-specific meetings
                    and email_notes.

    Returns
    -------
    RetrievedContext
        Fully populated dataclass. Never raises — on Supabase error,
        returns an empty context with retrieval_confidence=0.0.

    Notes
    -----
    - EC-13: all historical records are returned, not just recent ones.
      The planner is responsible for deciding which records are still active.
    - EC-27: inactive applications (rejected / expired / withdrawn) are
      included in ctx.applications but excluded from ctx.active_applications.
    - EC-28: all applications for the company are returned as a list.
    """
    ctx = RetrievedContext()

    try:
        # ------------------------------------------------------------------
        # 1. Resolve company name → canonical company_id
        # ------------------------------------------------------------------
        if company_name:
            resolved = resolve_company(company_name)
            if resolved.canonical_id and resolved.resolution in (
                "exact_alias", "exact_name", "fuzzy_high"
            ):
                ctx.company_id = resolved.canonical_id
            # fuzzy_low / no_match → company_id stays None
            # The planner will see low retrieval_confidence and act accordingly

        # ------------------------------------------------------------------
        # 2. Contact lookup by sender email
        # ------------------------------------------------------------------
        contact = get_contact_by_email(sender_email) if sender_email else None
        ctx.contact = contact
        contact_id = contact.get("id") if contact else None

        # ------------------------------------------------------------------
        # 3. Recruiter record (if contact exists)
        # ------------------------------------------------------------------
        if contact_id:
            ctx.recruiter = get_recruiter_by_contact(contact_id)

        # ------------------------------------------------------------------
        # 4. Applications — all for this company (EC-28 multi-app support)
        # ------------------------------------------------------------------
        if ctx.company_id:
            all_apps = get_applications_by_company(ctx.company_id)
            ctx.applications = all_apps or []

            # EC-27: separate active from historical
            inactive_statuses = {"rejected", "withdrawn", "expired"}
            ctx.active_applications = [
                a for a in ctx.applications
                if a.get("status", "applied") not in inactive_statuses
            ]

        # ------------------------------------------------------------------
        # 5. Active applications globally (fallback when no company_id)
        #    Used by planner to spot if user is generally active on job market
        # ------------------------------------------------------------------
        # (only populate if we have no company-specific results)
        if not ctx.applications and contact_id:
            # Best effort: look for any application linked to this contact
            # via the recruiter row's application_id
            if ctx.recruiter and ctx.recruiter.get("application_id"):
                linked_app_id = ctx.recruiter["application_id"]
                # Fetch using the active applications list and filter
                all_active = get_active_applications()
                ctx.active_applications = [
                    a for a in all_active if a.get("id") == linked_app_id
                ]
                ctx.applications = ctx.active_applications

        # ------------------------------------------------------------------
        # 6. Meetings — thread-specific first, then contact-level
        # ------------------------------------------------------------------
        if thread_id:
            from backend.memory.db import get_meeting_by_thread
            thread_meeting = get_meeting_by_thread(thread_id)
            if thread_meeting:
                ctx.meetings = [thread_meeting]

        # ------------------------------------------------------------------
        # 7. Conference submissions (EC-12: follow-up support)
        # ------------------------------------------------------------------
        if company_name:
            # Try by conference name (company_name may be org name)
            conf = get_conference_by_name(company_name)
            if conf:
                ctx.conference_submissions = [conf]

        if not ctx.conference_submissions:
            # Fetch all active submissions — planner will filter
            ctx.conference_submissions = get_active_conference_submissions() or []

        # ------------------------------------------------------------------
        # 8. Email notes — by contact and by thread
        # ------------------------------------------------------------------
        notes: list[dict] = []
        if contact_id:
            notes.extend(get_notes_by_contact(contact_id) or [])
        if thread_id:
            thread_notes = get_notes_by_thread(thread_id) or []
            # Deduplicate by id
            existing_ids = {n["id"] for n in notes}
            notes.extend(n for n in thread_notes if n["id"] not in existing_ids)
        ctx.email_notes = notes

        # ------------------------------------------------------------------
        # 9. Unverified events for this sender
        # ------------------------------------------------------------------
        all_unverified = get_unverified_events() or []
        ctx.unverified_events = [
            e for e in all_unverified
            if e.get("sender_email") == sender_email
            or (thread_id and e.get("thread_id") == thread_id)
        ]

        # ------------------------------------------------------------------
        # 10. Score confidence and build summary
        # ------------------------------------------------------------------
        ctx.retrieval_confidence = _score_confidence(ctx)
        ctx.retrieval_summary = _build_summary(ctx)

    except Exception as exc:
        ctx.retrieval_confidence = 0.0
        ctx.retrieval_summary = f"Context retrieval failed: {exc}"

    return ctx