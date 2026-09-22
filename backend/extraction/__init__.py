"""
backend.extraction

Public interface:
  extract_entities(email_text, category, thread_id=None) → EntityResult

Schemas (for type hints in other modules):
  RecruiterEntity, ApplicationEntity, MeetingEntity, ConferenceEntity, GeneralEntity
"""

from backend.extraction.extractor import extract_entities
from backend.extraction.schemas import (
    RecruiterEntity,
    ApplicationEntity,
    MeetingEntity,
    ConferenceEntity,
    GeneralEntity,
    EntityResult,
)

__all__ = [
    "extract_entities",
    "RecruiterEntity",
    "ApplicationEntity",
    "MeetingEntity",
    "ConferenceEntity",
    "GeneralEntity",
    "EntityResult",
]