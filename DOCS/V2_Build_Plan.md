# AI Email Agent — V2 Build Plan
## "Personalized Assistant" Phase-by-Phase Roadmap

> This document is the canonical day-by-day build plan for V2.
> Each phase is a self-contained milestone with a clear goal, deliverables, and test criteria.
> No phase begins until the previous one is confirmed working.

---

## V2 Goal

Upgrade the baseline V1 pipeline into a personalized, reasoning-first assistant by adding:
- Structured memory (Supabase PostgreSQL)
- Entity extraction
- A planner module
- Reply verification
- A fine-tuned Mistral 7B model (QLoRA, trained on Enron dataset via Google Colab)

---

## V2 Pipeline (target end state)

```
Gmail API / Mock
      │
      ▼
   Parser
      │
      ▼
  Classifier
      │
      ├──► Entity Extraction ──► Structured Memory (Supabase)
      │                                    │
      │                              Memory Read
      │                                    │
      ▼                                    ▼
   Planner  ◄──────────────────── Retrieved Context
      │
      ▼
Prompt Builder (V2: planner-aware)
      │
      ▼
Fine-Tuned Mistral 7B (via Ollama)
      │
      ▼
Reply Verification
      │
      ▼
Human Review UI (approve / edit / reject)
```

---

## Phase Overview

| Phase | Theme                        | Duration  | Key Output                          |
|-------|------------------------------|-----------|--------------------------------------|
| 1     | Supabase Schema & CRUD       | Day 1     | Database live, CRUD tested           |
| 2     | Entity Extraction            | Day 2     | Structured entities from any email   |
| 3     | Memory Read / Write          | Day 3     | Entities flowing into Supabase       |
| 4     | Planner Module               | Day 4–5   | Structured decision object per email |
| 5     | V2 Prompt Builder            | Day 6     | Planner-aware prompts                |
| 6     | Fine-Tuning Pipeline (Colab) | Day 7–9   | Fine-tuned GGUF model in Ollama      |
| 7     | Reply Verification           | Day 10    | Hallucination flags before review    |
| 8     | Dashboard V2 Upgrades        | Day 11    | Planner panel + verification UI      |
| 9     | Integration & End-to-End     | Day 12    | Full V2 pipeline working             |

> Phase 6 (fine-tuning) runs on Colab and is mostly waiting time.
> Overlap it with Phases 4–5 on the backend.

---

## Phase 1 — Supabase Schema & CRUD Layer

**Goal:** Get the database designed, deployed, and testable before any code that touches it.

### What we build

- Supabase project creation and connection setup
- Full PostgreSQL schema with all V2 tables
- Python CRUD layer (`backend/memory/db.py`)
- Unit tests with mock data inserts and reads

### Tables

```sql
applications     (id, company, role, status, platform, application_date, application_id)
recruiters       (id, name, email, company_id, thread_id, first_contact_date)
contacts         (id, name, email, company_id, notes)
meetings         (id, title, scheduled_time, participants, thread_id, status)
deadlines        (id, label, due_date, linked_entity_id, linked_entity_type, status)
entity_aliases   (id, canonical_id, alias, entity_type, confidence)
planner_logs     (id, email_id, decisions_json, created_at)
```

### Files created

```
backend/
  memory/
    __init__.py
    db.py          ← all CRUD functions
    schema.sql     ← full DDL (also run in Supabase dashboard)
  config.py        ← add SUPABASE_URL, SUPABASE_KEY
```

### Test criteria

- [ ] All tables created in Supabase dashboard
- [ ] `db.py` can insert and read back a mock application record
- [ ] `db.py` can insert and read back a mock recruiter record
- [ ] Entity alias insert + lookup works
- [ ] No hardcoded credentials — all from `.env`

---

## Phase 2 — Entity Extraction

**Goal:** Given any classified email, extract structured entities as a typed Python dict.

### What we build

- An extractor module that calls Mistral via Ollama with a strict JSON prompt
- Entity schemas as Pydantic models
- Extraction logic per email category (recruiter, meeting, conference, internship, professor)
- Unit tests against mock emails

### Entity schemas (Pydantic)

```python
class ApplicationEntity(BaseModel):
    company: str
    role: str
    platform: str | None
    application_id: str | None
    application_date: str | None

class RecruiterEntity(BaseModel):
    recruiter_name: str
    recruiter_email: str
    company: str
    role: str | None

class MeetingEntity(BaseModel):
    title: str
    scheduled_time: str | None
    participants: list[str]
    thread_id: str | None

class DeadlineEntity(BaseModel):
    label: str
    due_date: str
    linked_context: str | None
```

### Files created

```
backend/
  extraction/
    __init__.py
    extractor.py      ← main extract_entities(email, category) function
    schemas.py        ← Pydantic models for each entity type
    prompts.py        ← extraction prompt templates per category
```

### Test criteria

- [ ] Given a mock recruiter email → returns `RecruiterEntity` with correct fields
- [ ] Given a mock application acknowledgment → returns `ApplicationEntity`
- [ ] Given a mock meeting confirmation → returns `MeetingEntity`
- [ ] Gracefully handles missing fields (null, not crash)
- [ ] Returns raw dict if JSON parsing fails (fallback, no exception)

---

## Phase 3 — Memory Read / Write

**Goal:** Wire entity extraction output into Supabase. Handle deduplication, updates, and entity resolution.

### What we build

- `memory_writer.py` — decides whether to insert new record or update existing
- `memory_reader.py` — retrieves relevant context for a given email/sender
- Entity resolution logic — fuzzy company name matching (EC-10, EC-11)
- Thread continuation check — don't create duplicate records for the same thread (EC-9, EC-25)

### How entity resolution works

```
Incoming company name: "ABC Tech"
  ↓
Check entity_aliases table for fuzzy match
  ↓
Match found (canonical: "ABC Technologies", confidence: 0.92)?
  → High confidence → auto-accept → use canonical ID
  → Low confidence → flag for user confirmation → store pending
```

### Files created

```
backend/
  memory/
    memory_writer.py    ← insert_or_update(entity, category)
    memory_reader.py    ← retrieve_context(sender_email, company, thread_id)
    entity_resolver.py  ← resolve_company(name) → canonical_id or None
```

### Test criteria

- [ ] New recruiter email → new record in `recruiters` table
- [ ] Follow-up email from same recruiter → updates existing record, no duplicate
- [ ] "ABC Tech" resolves to "ABC Technologies" via alias table
- [ ] Low-confidence match → flagged, not auto-accepted
- [ ] `retrieve_context()` returns correct prior application given sender email

---

## Phase 4 — Planner Module

**Goal:** Replace V1's implicit reply logic with an explicit, structured reasoning step.

### What we build

- `PlannerDecision` Pydantic model (the planner's output contract)
- Planner logic that reads email + entities + retrieved context and outputs a decision
- Edge case handling baked into planner logic (EC-1 through EC-33 where relevant)
- Planner logs written to Supabase `planner_logs` table after every decision

### PlannerDecision schema

```python
class PlannerDecision(BaseModel):
    reply_required: bool
    reply_strategy: Literal["generate", "clarify", "no_reply"]
    memory_action: Literal["store_new", "update_existing", "skip"]
    calendar_check_needed: bool
    retrieval_needed: bool
    retrieval_query: str | None
    confidence: float          # 0.0 – 1.0
    constraints: list[str]     # e.g. ["do not commit to a date"]
    generation_strategy: Literal["fine_tuned"]   # V3 adds "rag", "hybrid"
    reasoning: str             # human-readable explanation (for dashboard)
```

### Planner decision logic (abbreviated)

```
If category == NEWSLETTER or PROMOTION:
    reply_required = False
    memory_action = skip

If category == ACKNOWLEDGMENT (EC-1, EC-5):
    reply_required = False
    memory_action = store_new (extract application/conference info)

If category == RECRUITER and no prior context:
    reply_required = True
    retrieval_needed = False
    confidence = medium

If category == RECRUITER and prior context found:
    reply_required = True
    retrieval_needed = True
    confidence = high

If calendar_check_needed and calendar status unknown (EC-16, EC-17, EC-33):
    constraints += ["do not commit to a date or time"]
    confidence = low

If retrieval returns nothing (EC-21):
    constraints += ["do not reference specific details not in email"]
```

### Files created

```
backend/
  planner/
    __init__.py
    planner.py          ← plan(email, entities, context) → PlannerDecision
    decision_schema.py  ← PlannerDecision Pydantic model
    edge_case_rules.py  ← rule functions for each EC category
```

### Test criteria

- [ ] Newsletter email → `reply_required=False`, `memory_action=skip`
- [ ] Acknowledgment email → `reply_required=False`, `memory_action=store_new`
- [ ] Recruiter email with no prior context → `reply_required=True`, `confidence < 0.6`
- [ ] Meeting request with empty calendar → `constraints` includes date commitment warning
- [ ] Every decision written to `planner_logs`
- [ ] `reasoning` field is a clear human-readable sentence

---

## Phase 5 — V2 Prompt Builder

**Goal:** Upgrade the V1 prompt builder to consume planner output and retrieved context.

### What changes from V1

V1 prompt builder takes: `(email_text, category)`

V2 prompt builder takes: `(email_text, category, planner_decision, retrieved_context)`

The prompt now includes:
- Retrieved prior context (applications, recruiter history, meetings)
- Planner constraints (e.g. "do not commit to a specific date")
- Confidence signal (low confidence → prompt tells model to hedge or ask for clarification)

### Example V2 prompt structure

```
You are a professional email assistant.

## Context from memory
- Applied to {company} for {role} on {date} via {platform}
- Prior email from this recruiter on {date}: "{summary}"

## Constraints
- Do not commit to any specific date or time.
- Do not reference information not present in the email or context above.

## Email to reply to
{email_body}

## Task
Write a professional reply. Be concise. Do not hallucinate facts.
```

### Files modified

```
backend/
  generation/
    prompt_builder.py    ← upgraded to accept PlannerDecision + context
```

### Test criteria

- [ ] Prompt includes retrieved context when available
- [ ] Prompt includes constraint list from planner
- [ ] Low-confidence planner decision → prompt instructs hedging language
- [ ] No-context email → prompt does not invent placeholder details

---

## Phase 6 — Fine-Tuning Pipeline (Google Colab)

**Goal:** Produce a QLoRA fine-tuned Mistral 7B model that generates professional email replies,
converted to GGUF and loaded into Ollama for local inference.

> This phase runs entirely on Google Colab. It is separate from the backend codebase.

### Sub-steps

#### 6a — Dataset Preparation
- Download Enron email dataset
- Filter to professional reply pairs (email → reply)
- Format into instruction-tuning format:
  ```json
  {"instruction": "Reply to this email professionally.", "input": "<email>", "output": "<reply>"}
  ```
- Target: ~5,000–10,000 clean pairs
- Save as `enron_finetune.jsonl`

#### 6b — QLoRA Training on Colab
- Base model: `mistralai/Mistral-7B-Instruct-v0.2`
- Quantization: 4-bit NF4 (BitsAndBytes)
- LoRA config: rank=16, alpha=32, dropout=0.05
- Optimizer: AdamW, lr=2e-4, cosine scheduler
- Epochs: 3–5, batch size 4 (via gradient accumulation ×4)
- Max sequence length: 2048
- Mixed precision: BF16
- Save best checkpoint, early stopping enabled

#### 6c — Adapter Push & Merge
- Push LoRA adapter to HuggingFace Hub: `kausan18/mistral-email-v2`
- Merge adapter into base model weights
- Save merged model locally on Colab

#### 6d — GGUF Conversion
- Clone `llama.cpp` on Colab
- Convert merged model → `mistral-email-v2.Q4_K_M.gguf`
- Download GGUF to local machine

#### 6e — Load into Ollama
```
# Create Modelfile
FROM ./mistral-email-v2.Q4_K_M.gguf
SYSTEM "You are a professional email assistant."

# Register model
ollama create mistral-email-v2 -f Modelfile

# Update backend config
OLLAMA_MODEL=mistral-email-v2
```

### Test criteria

- [ ] Training loss decreases across epochs (no divergence)
- [ ] Adapter pushed to HuggingFace successfully
- [ ] GGUF loaded in Ollama and responds to `ollama run mistral-email-v2`
- [ ] Reply quality visibly better than base model on 5 test emails

---

## Phase 7 — Reply Verification

**Goal:** Catch hallucinations and unsafe commitments before the user sees the draft.

### What we build

A verifier that takes `(reply_text, planner_decision, retrieved_context)` and returns a list of flags.

### Verification checks

| Check | Method | Flag label |
|---|---|---|
| Date/time commitment without calendar confirmation | Regex (tomorrow, Monday, 3 PM, etc.) | `DATE_COMMITMENT` |
| Company name mismatch | String match vs retrieved context | `WRONG_COMPANY` |
| Claims fact not in email or context | LLM second-pass check | `UNSUPPORTED_CLAIM` |
| Mentions person not in email or context | NER + context check | `UNKNOWN_PERSON` |
| Overly informal tone for category | Classifier | `TONE_MISMATCH` |

### Files created

```
backend/
  verification/
    __init__.py
    verifier.py         ← verify(reply, planner_decision, context) → list[Flag]
    flag_schema.py      ← Flag Pydantic model (label, severity, excerpt)
    checks/
      date_check.py
      company_check.py
      claim_check.py
```

### Test criteria

- [ ] Reply saying "see you Tuesday at 3 PM" with no calendar confirmation → `DATE_COMMITMENT` flag
- [ ] Reply mentioning wrong company → `WRONG_COMPANY` flag
- [ ] Clean reply with no issues → empty flag list
- [ ] Flags are surfaced in the review UI, not silently dropped

---

## Phase 8 — Dashboard V2 Upgrades

**Goal:** Surface the new V2 information (planner reasoning, verification flags) in the existing Next.js dashboard.

### What changes

**Email detail page (`/email/:id`)**
- Add "Planner Decision" panel: shows `reasoning`, `confidence` score, `constraints` list
- Add "Verification" panel: shows flags with severity badges
- Confidence score rendered as a colored indicator (green / amber / red)

**Inbox page (`/inbox`)**
- Add a "memory stored" badge on emails where `memory_action != skip`

**New page: `/uncertain`** (already planned in V1 dashboard design)
- Lists emails where `confidence < 0.5` or `reply_strategy == "clarify"`
- User can confirm entity matches, approve planner decisions

### Files modified

```
frontend/
  app/
    email/[id]/page.tsx         ← add PlannerPanel + VerificationPanel components
    inbox/page.tsx              ← add memory badge
    uncertain/page.tsx          ← new page
  components/
    PlannerPanel.tsx            ← new
    VerificationPanel.tsx       ← new
    ConfidenceBadge.tsx         ← new
```

### Test criteria

- [ ] Planner reasoning visible on email detail page
- [ ] Confidence score renders correctly for high/medium/low
- [ ] Verification flags show on detail page with severity
- [ ] `/uncertain` page lists low-confidence emails

---

## Phase 9 — Integration & End-to-End

**Goal:** Wire all V2 modules together and run the full pipeline against real emails.

### Integration order

1. Email in → classifier → entity extractor → memory writer
2. Memory reader retrieves context for email sender/company
3. Planner receives email + entities + context → produces `PlannerDecision`
4. Prompt builder receives planner decision → builds V2 prompt
5. Fine-tuned Mistral generates reply
6. Verifier checks reply → produces flags
7. All of the above surfaces in dashboard
8. User reviews, edits, approves → reply logged

### Integration test checklist

- [ ] Recruiter email flows through all 8 steps without exception
- [ ] Application acknowledgment: no reply generated, memory stored
- [ ] Newsletter: no reply, no memory
- [ ] Meeting request with empty calendar: reply hedges on time, `DATE_COMMITMENT` flag absent
- [ ] Second email from same recruiter: memory updated, not duplicated
- [ ] Planner log written to Supabase for every email processed
- [ ] Dashboard shows correct planner panel and verification flags

---

## File Structure at V2 completion

```
ai-email-agent/
  backend/
    ingestion/         (V1 — unchanged)
    classification/    (V1 — unchanged)
    extraction/        (NEW — Phase 2)
      extractor.py
      schemas.py
      prompts.py
    memory/            (NEW — Phase 1 + 3)
      db.py
      memory_writer.py
      memory_reader.py
      entity_resolver.py
      schema.sql
    planner/           (NEW — Phase 4)
      planner.py
      decision_schema.py
      edge_case_rules.py
    generation/        (UPGRADED — Phase 5)
      prompt_builder.py
    verification/      (NEW — Phase 7)
      verifier.py
      flag_schema.py
      checks/
    review/            (V1 — minor additions)
      approval_router.py
    config.py          (UPGRADED — Supabase keys added)
    main.py            (UPGRADED — new routes)
  frontend/
    app/
      inbox/           (UPGRADED — Phase 8)
      email/[id]/      (UPGRADED — Phase 8)
      uncertain/       (NEW — Phase 8)
    components/        (NEW — Phase 8)
  colab/               (NEW — Phase 6, separate from backend)
    prepare_dataset.ipynb
    train_qlora.ipynb
    convert_gguf.ipynb
```

---

## Branch Strategy

```
main                    ← protected, only merged PRs
  └── v2/phase-1-db         ← Phase 1 work
  └── v2/phase-2-extraction  ← Phase 2 work
  └── v2/phase-3-memory      ← Phase 3 work
  └── v2/phase-4-planner     ← Phase 4 work
  └── v2/phase-5-prompts     ← Phase 5 work
  └── v2/phase-6-finetune    ← Phase 6 (Colab notebooks only)
  └── v2/phase-7-verify      ← Phase 7 work
  └── v2/phase-8-dashboard   ← Phase 8 work
  └── v2/phase-9-integration ← Phase 9 integration
```

Each phase branch is merged to `main` only after its test criteria pass.

---

## Environment Variables Added in V2

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# Model (updated after Phase 6)
OLLAMA_MODEL=mistral-email-v2   # was: mistral

# Phase flags
USE_GMAIL=True
USE_PLANNER=True                # set False to bypass planner during testing
USE_VERIFICATION=True           # set False to bypass verifier during testing
```

---

## V2 Success Criteria

| Metric | Target |
|---|---|
| Recruiter email → correct entity extracted | > 90% accuracy on test set |
| Memory deduplication | Zero duplicate records across 20 test emails |
| Planner decision matches expected | > 85% on edge case test suite |
| Verification catches date commitments | 100% recall on test set |
| Fine-tuned model reply quality | Visibly better tone/personalization vs base model |
| End-to-end pipeline latency | < 15 seconds per email |
| Zero hallucinated company names | Verified by verification module |
