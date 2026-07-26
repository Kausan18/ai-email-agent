from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ---------------------------------------------------------------------------
# EmailCategory
# ---------------------------------------------------------------------------
# Defines every category the classifier can assign to an incoming email.
# Using an Enum here means:
#   - The classifier can only return one of these exact values
#   - The prompt builder can switch on it safely
#   - The frontend can render a badge without worrying about typos
#
# V2/V3 may expand this list — just add a new value here and the rest
# of the system picks it up automatically.
# ---------------------------------------------------------------------------

class EmailCategory(str, Enum):
    RECRUITER    = "recruiter"
    INTERNSHIP   = "internship"
    MEETING      = "meeting"
    PROFESSOR    = "professor"
    CONFERENCE   = "conference"
    REMINDER     = "reminder"
    NEWSLETTER   = "newsletter"
    PROMOTION    = "promotion"
    PERSONAL     = "personal"
    UNKNOWN      = "unknown"


# ---------------------------------------------------------------------------
# EmailSender
# ---------------------------------------------------------------------------
# Represents who sent the email.
# Keeping this as its own model means in V2 we can attach recruiter/contact
# records to it without changing anything downstream.
# ---------------------------------------------------------------------------

class EmailSender(BaseModel):
    name:  Optional[str] = None     # "John Smith" — may be absent
    email: str                      # "john@company.com" — always present


# ---------------------------------------------------------------------------
# CanonicalEmail
# ---------------------------------------------------------------------------
# The single, normalized representation of an email in this system.
#
# Whether the email comes from:
#   - Gmail API (V1 end)
#   - Mock JSON (V1 dev)
#   - Enron dataset (V2 training)
#
# ...it MUST be converted into this shape before anything else touches it.
#
# Fields:
#   id            — unique identifier (Gmail message ID or mock UUID)
#   thread_id     — groups emails in the same conversation
#   sender        — who sent it
#   recipients    — list of To: addresses
#   subject       — email subject line
#   body          — plain text body (HTML stripped)
#   timestamp     — when it was received
#   is_reply      — is this part of an ongoing thread?
#   raw_headers   — optional, kept for debugging Gmail parsing issues
# ---------------------------------------------------------------------------

class CanonicalEmail(BaseModel):
    id:           str
    thread_id:    Optional[str]        = None
    sender:       EmailSender
    recipients:   list[str]            = Field(default_factory=list)
    subject:      str
    body:         str
    timestamp:    datetime
    is_reply:     bool                 = False
    raw_headers:  Optional[dict]       = None   # Only populated from Gmail


# ---------------------------------------------------------------------------
# ClassifiedEmail
# ---------------------------------------------------------------------------
# Output of the classification module.
# Wraps CanonicalEmail and adds the classifier's decision.
#
# Fields:
#   email          — the original canonical email (unchanged)
#   category       — what type of email this is
#   reply_required — should the agent generate a reply?
#   confidence     — how confident is the classifier? (0.0 – 1.0)
#                    V1: rule-based, so this will be 1.0 or 0.5
#                    V3: confidence engine gives real scores
#   reason         — human-readable explanation of why this category
#                    was chosen. Shown on the dashboard for explainability.
# ---------------------------------------------------------------------------

class ClassifiedEmail(BaseModel):
    email:          CanonicalEmail
    category:       EmailCategory
    reply_required: bool
    confidence:     float              = Field(ge=0.0, le=1.0)
    reason:         str                = ""