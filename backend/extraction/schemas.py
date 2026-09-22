"""
Entity schemas for Phase 2 extraction.

Each schema represents the structured facts we want to pull out of
a classified email. All fields that may be absent are Optional —
the extractor must never crash on a missing field (EC-21).

extraction_confidence is present on every entity:
  >= 0.75  → high   (all or most fields populated, clean JSON)
   0.4–0.74 → medium (several fields null, or minor parse issues)
  < 0.4    → low    (JSON fallback used, or nearly everything null)

This signal flows into the Planner in Phase 4.
"""

from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# RECRUITER  (category: RECRUITER)
# Cold outreach or follow-up from a recruiter at a company.
# ---------------------------------------------------------------------------

class RecruiterEntity(BaseModel):
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None               # role they are recruiting for
    job_location: Optional[str] = None
    next_step: Optional[str] = None          # "interview", "phone screen", etc.
    deadline: Optional[str] = None           # ISO date string if mentioned
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# APPLICATION  (category: INTERNSHIP)
# Automated acknowledgment that an application was received.
# No reply is required (EC-1, EC-5) but facts must be stored.
# ---------------------------------------------------------------------------

class ApplicationEntity(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    platform: Optional[str] = None           # Internshala, LinkedIn, etc.
    application_id: Optional[str] = None
    application_date: Optional[str] = None   # ISO date string
    status: str = "applied"                  # always "applied" at ingestion
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# MEETING  (category: MEETING)
# A meeting invite, confirmation, or reschedule request.
# ---------------------------------------------------------------------------

class MeetingEntity(BaseModel):
    title: Optional[str] = None
    scheduled_time: Optional[str] = None     # ISO datetime string if parseable
    duration_minutes: Optional[int] = None
    location_or_link: Optional[str] = None   # room name, Zoom link, etc.
    participants: list[str] = []             # list of email addresses or names
    organizer: Optional[str] = None
    agenda: Optional[str] = None
    thread_id: Optional[str] = None          # populated by extractor caller, not LLM
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# CONFERENCE  (category: CONFERENCE)
# A submission acknowledgment, acceptance, or organizer follow-up.
# EC-6, EC-12: store paper title, deadlines, status.
# ---------------------------------------------------------------------------

class ConferenceEntity(BaseModel):
    conference_name: Optional[str] = None
    paper_title: Optional[str] = None
    submission_id: Optional[str] = None
    submission_date: Optional[str] = None    # ISO date string
    status: Optional[str] = None            # submitted, accepted, rejected, etc.
    camera_ready_deadline: Optional[str] = None
    presentation_date: Optional[str] = None
    organizer_email: Optional[str] = None
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# GENERAL  (categories: PROFESSOR, PERSONAL, UNKNOWN, and fallback)
# Catch-all for anything that doesn't map cleanly to the above.
# Also used when the classifier returns an unexpected category.
# ---------------------------------------------------------------------------

class GeneralEntity(BaseModel):
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    topic: Optional[str] = None             # one-sentence summary of what the email is about
    action_items: list[str] = []            # anything the user needs to do
    mentioned_dates: list[str] = []         # any dates or deadlines mentioned
    notes: Optional[str] = None             # free-text catch-all
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Union type — what extract_entities() returns.
# None is returned for NEWSLETTER / PROMOTION — no extraction performed.
# ---------------------------------------------------------------------------

EntityResult = RecruiterEntity | ApplicationEntity | MeetingEntity | ConferenceEntity | GeneralEntity | None