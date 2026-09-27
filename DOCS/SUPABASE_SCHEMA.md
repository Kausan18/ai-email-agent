# Supabase Schema Reference
## AI Email Agent — V2 Ground Truth

> This file is the canonical reference for every table and column in the
> Supabase database. Before writing any code that calls `db.py`, verify
> your column keys against this file. Mismatches caused every bug in Phase 3.
>
> Last verified: Phase 3 completion (all 10 tests passing).
> Update this file whenever a migration adds or removes a column.

---

## How to verify against live DB

Run this in the Supabase SQL Editor at any time:

```sql
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

---

## Table: `companies`

Canonical organisation identity. All other tables reference this by UUID.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| name | text | NO (unique) |
| domain | text | YES |
| created_at | timestamptz | NO |

**Notes**
- `upsert_company({"name": ..., "domain": ...})` — domain optional
- Never pass `"domain": None` — use None-stripping in db.py

---

## Table: `contacts`

Every person encountered in the inbox.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| email | text | NO (unique) |
| name | text | YES |
| company_id | uuid | YES (FK → companies) |
| relationship_type | text | YES |
| created_at | timestamptz | NO |

**Valid `relationship_type` values**
`recruiter` · `professor` · `colleague` · `friend` · `conference_organizer` · `unknown`

**Notes**
- `upsert_contact({"email": ..., "name": ..., "company_id": ..., "relationship_type": ...})`
- `contact_id` is nullable in email_notes for unknown senders (EC-18)

---

## Table: `recruiters`

Extends contacts for recruiter-specific metadata.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| contact_id | uuid | NO (FK → contacts) |
| company_id | uuid | YES (FK → companies) |
| thread_id | text | YES |
| first_contact_date | timestamptz | YES |
| application_id | uuid | YES (FK → applications) |
| created_at | timestamptz | NO |

**Notes**
- `application_id` is intentionally nullable — cold outreach arrives before any application (EC-8)
- ❌ NO `role` column — role lives on the application row, not the recruiter row
- ❌ NO `next_step` column
- ❌ NO `deadline` column
- Deduplication key: `contact_id` (one recruiter record per contact)

---

## Table: `applications`

Job and internship applications with full status lifecycle.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| company_id | uuid | YES (FK → companies) |
| role | text | YES |
| status | text | YES |
| platform | text | YES |
| application_id | text | YES |
| application_date | text | YES |
| notes | text | YES |
| thread_id | text | YES |
| created_at | timestamptz | NO |
| updated_at | timestamptz | NO |

**Valid `status` values**
`applied` · `screening` · `interview` · `offer` · `rejected` · `withdrawn` · `expired`

**Notes**
- ❌ NO `application_id_external` — the column is simply `application_id`
- `thread_id` was added during Phase 3 via `ALTER TABLE applications ADD COLUMN thread_id TEXT`
- Deduplication key: `(company_id, role)` — checked in memory_writer before insert
- `updated_at` is managed by Supabase DEFAULT — never send it in update payloads

---

## Table: `meetings`

Extracted meeting records.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| title | text | YES |
| scheduled_time | text | YES |
| participants | text[] | YES |
| thread_id | text | YES |
| status | text | YES |
| created_at | timestamptz | NO |
| updated_at | timestamptz | NO |

**Notes**
- ❌ NO `duration_minutes` column
- ❌ NO `location_or_link` column
- ❌ NO `organizer` column
- ❌ NO `agenda` column
- Deduplication key: `thread_id` — checked via `get_meeting_by_thread()` before insert (EC-9)
- `updated_at` managed by Supabase DEFAULT

---

## Table: `conference_submissions`

Academic paper submissions.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| conference_name | text | YES |
| paper_title | text | YES |
| submission_id | text | YES |
| status | text | YES |
| submission_date | text | YES |
| created_at | timestamptz | NO |

**Valid `status` values**
`submitted` · `under_review` · `accepted` · `rejected` · `withdrawn`

**Notes**
- `get_conference_by_name()` orders by `created_at DESC` — always returns freshest row
- EC-19: if no prior submission found, routes to `unverified_events` instead

---

## Table: `entity_aliases`

Maps fuzzy name variants to canonical company UUIDs.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| canonical_id | uuid | NO (FK → companies) |
| alias | text | NO |
| entity_type | text | NO |
| confidence | float | YES |
| created_at | timestamptz | NO |

**Notes**
- Confidence >= 0.85: auto-accept (fuzzy_high)
- Confidence 0.50–0.84: flag for user review (fuzzy_low)
- Confidence < 0.50: no match, create new company record

---

## Table: `email_notes`

Catch-all free-text store for unstructured context.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| contact_id | uuid | YES (FK → contacts) |
| thread_id | text | YES |
| category | text | YES |
| summary | text | YES |
| raw_context | text | YES |
| email_date | text | YES |
| created_at | timestamptz | NO |

**Notes**
- ❌ NO `sender_email` column
- ❌ NO `sender_name` column
- ❌ NO `topic` column
- ❌ NO `action_items` column
- ❌ NO `mentioned_dates` column
- ❌ NO `notes` column
- `contact_id` nullable for unknown senders (EC-18)
- `category` maps to email category string (general, professor, colleague, etc.)
- `summary` is the human-readable one-liner; `raw_context` is the full extracted detail

---

## Table: `unverified_events`

Holding area for acknowledgments with no matching prior record (EC-19, EC-20).

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| email_id | text | **NO — NOT NULL CONSTRAINT** |
| event_type | text | YES |
| raw_data | jsonb | YES |
| reason | text | YES |
| created_at | timestamptz | NO |

**Notes**
- ❌ NO `sender_email` column at top level — put it inside `raw_data` JSON
- ❌ NO `thread_id` column at top level — put it inside `raw_data` JSON
- `email_id` is **required** — use `thread_id` as the value when inserting from the writer
- `raw_data` is JSONB — put all contextual detail here (company, role, sender, thread, etc.)
- Surfaces in `/uncertain` dashboard queue

---

## Table: `flagged_emails`

Phishing and suspicious emails (EC-32).

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| email_id | text | YES |
| reason | text | YES |
| sender | text | YES |
| reviewed | boolean | NO (default false) |
| flagged_at | timestamptz | NO |

---

## Table: `planner_logs`

Every planner decision stored as JSONB. Audit trail and future router training data.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| email_id | text | YES |
| decisions | jsonb | YES |
| created_at | timestamptz | NO |

---

## Table: `deadlines`

Time-bound obligations linked to any entity.

| Column | Type | Nullable |
|---|---|---|
| id | uuid | NO |
| label | text | YES |
| due_date | text | YES |
| linked_entity_id | uuid | YES |
| linked_entity_type | text | YES |
| status | text | YES |
| created_at | timestamptz | NO |

---

## Critical rules for all future phases

**Rule 1 — Always verify column names before writing code**
Run the `information_schema.columns` query above. Never assume a column exists
because it was in the PRD or a Pydantic schema field.

**Rule 2 — None-stripping on every insert/upsert**
```python
clean = {k: v for k, v in data.items() if v is not None}
result = _client().table("...").insert(clean).execute()
```
Never send `None` values to Postgres — they serialise as the string `"None"`
and crash UUID/timestamp columns.

**Rule 3 — Never send `updated_at` in update payloads**
Supabase manages this via `DEFAULT now()`. Sending `"updated_at": "NOW()"`
as a Python string literal is a type error that fails silently.

**Rule 4 — `unverified_events.email_id` is NOT NULL**
Always pass `"email_id": thread_id` when inserting unverified events.

**Rule 5 — FK-safe delete order for tests**
When cleaning up test data, always delete children before parents:
```
recruiters → applications → conference_submissions → meetings →
email_notes → unverified_events → entity_aliases → planner_logs →
contacts → companies
```
