-- ============================================================
-- AI Email Agent V2 — Structured Memory Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- Entity aliases: maps fuzzy company names to canonical IDs
CREATE TABLE IF NOT EXISTS entity_aliases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id UUID NOT NULL,
    alias        TEXT NOT NULL,
    entity_type  TEXT NOT NULL CHECK (entity_type IN ('company', 'person', 'conference')),
    confidence   FLOAT NOT NULL DEFAULT 1.0,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Companies (canonical records)
CREATE TABLE IF NOT EXISTS companies (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL UNIQUE,
    domain       TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Contacts (any person we've emailed with)
CREATE TABLE IF NOT EXISTS contacts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT,
    email        TEXT NOT NULL UNIQUE,
    company_id   UUID REFERENCES companies(id),
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Recruiters (contacts who are recruiters)
CREATE TABLE IF NOT EXISTS recruiters (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID NOT NULL REFERENCES contacts(id),
    company_id        UUID REFERENCES companies(id),
    thread_id         TEXT,
    first_contact_date TIMESTAMPTZ DEFAULT NOW(),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Applications (internship / job applications)
CREATE TABLE IF NOT EXISTS applications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID REFERENCES companies(id),
    role             TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'applied'
                     CHECK (status IN ('applied', 'screening', 'interview', 'offer', 'rejected', 'withdrawn', 'expired')),
    platform         TEXT,
    application_id   TEXT,
    application_date TIMESTAMPTZ,
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Meetings
CREATE TABLE IF NOT EXISTS meetings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          TEXT,
    scheduled_time TIMESTAMPTZ,
    participants   TEXT[],
    thread_id      TEXT,
    status         TEXT NOT NULL DEFAULT 'scheduled'
                   CHECK (status IN ('scheduled', 'completed', 'cancelled', 'rescheduled')),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Deadlines
CREATE TABLE IF NOT EXISTS deadlines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label               TEXT NOT NULL,
    due_date            TIMESTAMPTZ NOT NULL,
    linked_entity_id    UUID,
    linked_entity_type  TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'expired')),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Planner logs (one row per email processed)
CREATE TABLE IF NOT EXISTS planner_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id       TEXT NOT NULL,
    decisions      JSONB NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_contacts_email        ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_applications_company  ON applications(company_id);
CREATE INDEX IF NOT EXISTS idx_applications_status   ON applications(status);
CREATE INDEX IF NOT EXISTS idx_recruiters_company    ON recruiters(company_id);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias  ON entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_planner_logs_email    ON planner_logs(email_id);


-- Additions to the database

-- Add relationship type to existing contacts table
ALTER TABLE contacts
ADD COLUMN IF NOT EXISTS relationship_type TEXT DEFAULT 'unknown'
CHECK (relationship_type IN (
    'recruiter', 'professor', 'colleague',
    'friend', 'conference_organizer', 'unknown'
));

-- New table for unstructured email context
CREATE TABLE IF NOT EXISTS email_notes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id   UUID REFERENCES contacts(id),
    thread_id    TEXT,
    category     TEXT,
    summary      TEXT,
    raw_context  TEXT,
    email_date   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_notes_contact  ON email_notes(contact_id);
CREATE INDEX IF NOT EXISTS idx_email_notes_thread   ON email_notes(thread_id);

CREATE TABLE IF NOT EXISTS conference_submissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conference_name TEXT NOT NULL,
    paper_title     TEXT,
    submission_id   TEXT,
    status          TEXT NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted', 'under_review', 'accepted', 'rejected', 'withdrawn')),
    submission_date TIMESTAMPTZ,
    decision_date   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE recruiters
ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id);

CREATE TABLE IF NOT EXISTS unverified_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id     TEXT NOT NULL,
    event_type   TEXT NOT NULL,  -- 'application', 'conference', 'meeting'
    raw_data     JSONB NOT NULL,
    reason       TEXT,           -- why it couldn't be verified
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flagged_emails (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id     TEXT NOT NULL,
    reason       TEXT NOT NULL,  -- 'phishing', 'suspicious_link', 'unknown_sender', etc.
    sender       TEXT,
    flagged_at   TIMESTAMPTZ DEFAULT NOW(),
    reviewed     BOOLEAN DEFAULT FALSE
);