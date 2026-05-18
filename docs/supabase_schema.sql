-- ReplyRight Supabase Schema
-- Paste this into the Supabase SQL Editor and run it once to create all tables.
-- Project: ReplyRight (dxalumiijcfmwzmosijf)

-- ── feedback_events ──────────────────────────────────────────────────────────
-- One row per user correction. No PII: email bodies, guest names, reservation
-- numbers, and payment data are never stored here.
CREATE TABLE IF NOT EXISTS feedback_events (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email_fingerprint   TEXT NOT NULL,       -- SHA-256 of sender_domain+subject_tokens
    sender_domain       TEXT,                -- e.g. "alchemyconcierge.com"
    original_urgency    INTEGER,
    corrected_urgency   INTEGER,
    original_owner      TEXT,
    corrected_owner     TEXT,
    original_category   TEXT,
    corrected_category  TEXT,
    original_contact_type TEXT,
    corrected_contact_type TEXT,
    original_sentiment  TEXT,
    corrected_sentiment TEXT,
    original_status     TEXT,
    corrected_status    TEXT,
    summary_quality_rating INTEGER CHECK (summary_quality_rating BETWEEN 1 AND 5),
    reply_quality_rating INTEGER CHECK (reply_quality_rating BETWEEN 1 AND 5),
    confidence_score    INTEGER,             -- 10-95, from local heuristic
    feedback_notes      TEXT,               -- free-text correction note (no PII)
    analysis_engine     TEXT,               -- "local-triage", "openai", etc.
    app_version         TEXT DEFAULT '0.1.0',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index for pattern mining (sender domain + owner corrections)
CREATE INDEX IF NOT EXISTS idx_feedback_domain ON feedback_events (sender_domain);
CREATE INDEX IF NOT EXISTS idx_feedback_urgency ON feedback_events (corrected_urgency);
CREATE INDEX IF NOT EXISTS idx_feedback_category ON feedback_events (corrected_category);

-- Existing projects created before structured ratings can run these safely.
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS original_status TEXT;
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS corrected_status TEXT;
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS summary_quality_rating INTEGER CHECK (summary_quality_rating BETWEEN 1 AND 5);
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS reply_quality_rating INTEGER CHECK (reply_quality_rating BETWEEN 1 AND 5);

CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback_events (corrected_status);

-- ── classification_rules ─────────────────────────────────────────────────────
-- Approved rules downloaded by the app on startup to improve local triage.
CREATE TABLE IF NOT EXISTS classification_rules (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_key         TEXT NOT NULL UNIQUE,
    rule_type        TEXT NOT NULL,   -- "owner_by_domain", "category_correction", "urgency_correction"
    pattern          TEXT NOT NULL,   -- human-readable trigger description
    action           TEXT NOT NULL,   -- what the rule does
    confidence       INTEGER DEFAULT 0,
    correction_count INTEGER DEFAULT 0,
    status           TEXT DEFAULT 'approved' CHECK (status IN ('pending_review', 'approved', 'rejected')),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── known_senders ─────────────────────────────────────────────────────────────
-- Sender domain → contact type / owner mappings learned from feedback.
CREATE TABLE IF NOT EXISTS known_senders (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    sender_domain    TEXT NOT NULL UNIQUE,
    contact_type     TEXT,            -- "Travel agency", "Direct guest", etc.
    default_owner    TEXT,            -- preferred department owner
    correction_count INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_known_senders_domain ON known_senders (sender_domain);

-- prompt_versions -------------------------------------------------------------
-- Versioned prompt/config metadata downloaded at startup. Prompt text must not
-- include guest PII or local mailbox content.
CREATE TABLE IF NOT EXISTS prompt_versions (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    prompt_key      TEXT NOT NULL UNIQUE,
    version         TEXT NOT NULL,
    prompt_text     TEXT NOT NULL,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_status ON prompt_versions (status);

-- ── training_examples ─────────────────────────────────────────────────────────
-- Sanitized, redacted email bodies with classification labels.
-- No raw PII stored: bodies are redacted before upload.
-- Inserted by the admin training pipeline using the service role key.
CREATE TABLE IF NOT EXISTS training_examples (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email_fingerprint       TEXT NOT NULL UNIQUE,  -- SHA-256(sender_domain:subject_tokens)
    sender_domain           TEXT,
    subject_tokens          TEXT,                  -- sanitized keyword tokens, no PII
    body_redacted           TEXT NOT NULL,         -- PII-stripped body (max 4000 chars)
    label_urgency           INTEGER CHECK (label_urgency BETWEEN 1 AND 5),
    label_owner             TEXT,
    label_category          TEXT,
    label_status            TEXT,
    label_sentiment         TEXT,
    label_contact_type      TEXT,
    label_missing_info      BOOLEAN DEFAULT FALSE,
    label_reply_required    BOOLEAN DEFAULT FALSE,
    label_escalation_required BOOLEAN DEFAULT FALSE,
    labeling_engine         TEXT,                  -- "claude", "heuristic", "openai", "human"
    human_reviewed          BOOLEAN DEFAULT FALSE,
    app_version             TEXT DEFAULT '0.1.0',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_urgency  ON training_examples (label_urgency);
CREATE INDEX IF NOT EXISTS idx_training_owner    ON training_examples (label_owner);
CREATE INDEX IF NOT EXISTS idx_training_reviewed ON training_examples (human_reviewed);

-- Migration: add label_contact_type column if not present (safe to run on existing tables)
ALTER TABLE training_examples ADD COLUMN IF NOT EXISTS label_contact_type TEXT;

-- ── RLS: allow inserts from the publishable (anon) key ───────────────────────
-- Enable Row Level Security then allow anonymous inserts so the desktop app
-- can upload feedback without needing the service_role key.
ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE classification_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE known_senders ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_examples ENABLE ROW LEVEL SECURITY;

-- Drop policies before (re)creating so this script is safe to run multiple times.
DROP POLICY IF EXISTS "allow_insert_feedback"           ON feedback_events;
DROP POLICY IF EXISTS "allow_read_rules"                ON classification_rules;
DROP POLICY IF EXISTS "allow_read_senders"              ON known_senders;
DROP POLICY IF EXISTS "allow_read_active_prompts"       ON prompt_versions;
DROP POLICY IF EXISTS "allow_upsert_rules"              ON classification_rules;
DROP POLICY IF EXISTS "allow_update_rules"              ON classification_rules;
DROP POLICY IF EXISTS "allow_service_insert_training"   ON training_examples;
DROP POLICY IF EXISTS "allow_service_select_training"   ON training_examples;

-- Anyone can insert feedback (desktop app uses publishable key)
CREATE POLICY "allow_insert_feedback"
    ON feedback_events FOR INSERT TO anon WITH CHECK (true);

-- Anyone can read approved rules (app downloads them on startup)
CREATE POLICY "allow_read_rules"
    ON classification_rules FOR SELECT TO anon
    USING (status = 'approved');

-- Anyone can read known senders
CREATE POLICY "allow_read_senders"
    ON known_senders FOR SELECT TO anon USING (true);

-- Anyone can read active prompt versions
CREATE POLICY "allow_read_active_prompts"
    ON prompt_versions FOR SELECT TO anon
    USING (status = 'active');

-- ── Auto-promotion: app can upsert rule candidates without admin approval ─────
-- Run this block once after the initial schema if you want shared learning to
-- work automatically (no admin dashboard needed).
CREATE POLICY "allow_upsert_rules"
    ON classification_rules FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "allow_update_rules"
    ON classification_rules FOR UPDATE TO anon
    USING (true) WITH CHECK (true);

-- Training examples: only the service role key (admin app) may insert or read.
-- The anon/publishable key cannot touch this table.
CREATE POLICY "allow_service_insert_training"
    ON training_examples FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "allow_service_select_training"
    ON training_examples FOR SELECT TO service_role USING (true);
