"""
Extraction prompt templates — one per email category.

Design principles:
  - The JSON schema is shown explicitly inside the prompt.
    Mistral matches a visible schema far more reliably than a prose description.
  - Every prompt ends with the same hard rule:
    "Return ONLY the JSON object. No explanation. No markdown. No extra text."
  - Optional fields explicitly say "null if not present" — this prevents
    the model from inventing values (EC-29).
  - The system prompt keeps the model in extraction mode, not reply mode.

build_prompt(category, email_text) is the only public function.
"""

# ---------------------------------------------------------------------------
# System prompt — shared across all categories
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a structured information extractor for an email assistant.
Your only job is to read an email and extract specific facts into a JSON object.
You do not write replies. You do not summarise. You extract facts.
If a fact is not present in the email, return null for that field — do not invent or guess.
Return ONLY valid JSON. No markdown. No explanation. No extra text before or after the JSON."""


# ---------------------------------------------------------------------------
# Category-specific extraction prompts
# ---------------------------------------------------------------------------

_RECRUITER_PROMPT = """Extract recruiter information from the email below.

Return a JSON object with exactly these keys:
{{
  "recruiter_name": "full name of the recruiter, or null",
  "recruiter_email": "recruiter email address, or null",
  "company": "company or organisation name, or null",
  "role": "the job title or role being offered or discussed, or null",
  "job_location": "city, country, or 'Remote', or null",
  "next_step": "what happens next e.g. 'phone screen', 'technical interview', 'fill out form', or null",
  "deadline": "any deadline or response-by date in YYYY-MM-DD format, or null"
}}

Email:
{email_text}

Return ONLY the JSON object."""


_APPLICATION_PROMPT = """Extract internship or job application details from this acknowledgment email.

Return a JSON object with exactly these keys:
{{
  "company": "company or organisation name, or null",
  "role": "job title or internship role applied for, or null",
  "platform": "the platform where the application was submitted e.g. Internshala, LinkedIn, company website, or null",
  "application_id": "any application reference ID or ticket number, or null",
  "application_date": "date the application was submitted in YYYY-MM-DD format, or null"
}}

Email:
{email_text}

Return ONLY the JSON object."""


_MEETING_PROMPT = """Extract meeting details from the email below.

Return a JSON object with exactly these keys:
{{
  "title": "meeting title or subject, or null",
  "scheduled_time": "meeting date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS), or null",
  "duration_minutes": "duration in minutes as an integer, or null",
  "location_or_link": "physical location, room name, or video call link, or null",
  "participants": ["list of participant names or email addresses — empty list if none mentioned"],
  "organizer": "name or email of the person who scheduled the meeting, or null",
  "agenda": "brief description of meeting purpose or topics, or null"
}}

Email:
{email_text}

Return ONLY the JSON object."""


_CONFERENCE_PROMPT = """Extract academic conference submission details from the email below.

Return a JSON object with exactly these keys:
{{
  "conference_name": "full name of the conference, or null",
  "paper_title": "title of the submitted paper, or null",
  "submission_id": "submission ID or reference number, or null",
  "submission_date": "date of submission in YYYY-MM-DD format, or null",
  "status": "current status e.g. submitted, under_review, accepted, rejected — lowercase, or null",
  "camera_ready_deadline": "camera-ready or final version deadline in YYYY-MM-DD format, or null",
  "presentation_date": "presentation or conference date in YYYY-MM-DD format, or null",
  "organizer_email": "email address of the conference organizer or programme chair, or null"
}}

Email:
{email_text}

Return ONLY the JSON object."""


_GENERAL_PROMPT = """Extract key information from the email below.

Return a JSON object with exactly these keys:
{{
  "sender_name": "full name of the person who sent the email, or null",
  "sender_email": "email address of the sender, or null",
  "topic": "one sentence describing what this email is about, or null",
  "action_items": ["list of things the recipient needs to do — empty list if none"],
  "mentioned_dates": ["list of any dates or deadlines mentioned in YYYY-MM-DD format — empty list if none"],
  "notes": "any other important information not captured above, or null"
}}

Email:
{email_text}

Return ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Dispatch table — maps classifier category → prompt template
# ---------------------------------------------------------------------------

_PROMPT_MAP: dict[str, str] = {
    "RECRUITER":  _RECRUITER_PROMPT,
    "INTERNSHIP": _APPLICATION_PROMPT,
    "MEETING":    _MEETING_PROMPT,
    "CONFERENCE": _CONFERENCE_PROMPT,
    # Everything else falls through to general
    "PROFESSOR":  _GENERAL_PROMPT,
    "PERSONAL":   _GENERAL_PROMPT,
    "UNKNOWN":    _GENERAL_PROMPT,
}

# Categories that should never reach the extractor.
# extract_entities() returns None immediately for these.
NO_EXTRACT_CATEGORIES = {"NEWSLETTER", "PROMOTION"}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def build_prompt(category: str, email_text: str) -> tuple[str, str]:
    """
    Return (system_prompt, user_prompt) for the given category.

    Falls back to the general prompt if the category is unrecognised.
    Callers should check NO_EXTRACT_CATEGORIES before calling this.
    """
    template = _PROMPT_MAP.get(category.upper(), _GENERAL_PROMPT)
    user_prompt = template.format(email_text=email_text)
    return SYSTEM_PROMPT, user_prompt