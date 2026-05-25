# Training the Classifier — Agent Runbook

Last updated: 2026-05-25

## What this document is

This is the authoritative step-by-step training workflow for any agent (Claude, Codex, or human) asked to "train the classifier" or "run training."  If you're asked to train the ReplyRight email classifier, follow this document exactly.

## Overview

The running app has four phases, always in this order:

1. **Import** — pull ~1000 emails from the Outlook "Completed Request" folder into SQLite
2. **Label** — heuristic analysis assigns urgency, owner, category, sentiment labels
3. **Upload** — sanitized, redacted training examples are pushed to Supabase for review
4. **Purge** — raw imported emails are deleted from SQLite (they are large and transient)

After training examples are in Supabase and reviewed, the local classifier can be retrained from them.

When Brian explicitly tells Codex or Claude **"train the model"**, the agent may add an external agent-assisted review pass outside the running app. That means the agent uses its own model judgment to label or correct redacted/sanitized completed-request examples, writes only sanitized labels/examples back to the training store, retrains the local classifier, and purges raw imported bodies. This is not an in-app endpoint and is not part of Refresh Inbox.

## Privacy and safety invariants (never violate)

- Raw `body_text` is **never uploaded**. Only `body_redacted` is stored.
- Full sender email is **never stored**. Only `sender_domain`.
- Full subject is **never stored**. Only `subject_tokens`.
- In-app training endpoints **never call external AI providers** (no Claude, OpenAI, Google AI).
- Agent-assisted labeling is allowed only when Brian explicitly asks an agent to train the model. It must use redacted/sanitized content where possible and must not store raw bodies, full subjects, full sender emails, message IDs, reservation/payment identifiers, secrets, or private mailbox content in Supabase, docs, logs, or final responses.
- Outlook messages are read-only: do not send, delete, archive, move, or mark-read any message.

## Step 1: Import completed request emails

Call `run_completed_pipeline()` from `outlook_dashboard/completed_training_pipeline.py`.

**Via the admin API** (preferred when the app is running):

```http
POST /api/training/completed-pipeline
{
  "mailbox_name": "<mailbox display name>",
  "batch_size": 1000
}
```

**Via Python** (for agent scripts):

```python
from outlook_dashboard.completed_training_pipeline import run_completed_pipeline

result = run_completed_pipeline(
    mailbox_name="<mailbox display name>",
    folder_name="Completed Request",  # default
    batch_size=1000,
)
print(result)
# {imported, labeled, uploaded, skipped, failed, purged_email_rows, purged_export_files, ...}
```

`batch_size=1000` targets the 1000-email goal. Adjust if the folder has fewer emails.

The function does all four phases (import → label → upload → purge) in a single call.

## Step 2: Verify the upload

Check that examples were uploaded to Supabase:

```python
from outlook_dashboard.completed_training_pipeline import completed_pipeline_status
print(completed_pipeline_status())
# {processed, uploaded, labeled, failed, skipped, ...}
```

Or via the admin UI at `Settings → Training → Completed Requests Pipeline`.

## Step 3: Agent-assisted review when Brian asks an agent to train the model

If Brian's instruction is to Codex/Claude, not just the in-app admin UI, perform a review pass before retraining:

1. Work from the sanitized examples produced by `run_completed_pipeline()` or from redacted local extracts.
2. Use agent judgment to assign or correct the classifier targets: urgency, owner, category, status, missing-information, reply-required, and escalation/review signals.
3. Preserve the same privacy contract as the in-app pipeline: only redacted body text, sender domain, subject tokens, labels, and safe metadata may be written back.
4. Mark the resulting examples as agent-reviewed or human-review-needed in the safest available metadata field if the storage path supports it.
5. Do not call the app's single-email Claude suggestion path for bulk labeling.

If the agent cannot safely access Outlook, Supabase, or the local database, stop and report the blocker rather than inventing labels.

## Step 4: Retrain the local classifier

After examples are reviewed in Supabase, retrain:

```http
POST /api/training/train
```

Or via Python:

```python
from outlook_dashboard.local_classifier import train
result = train()
print(result)
```

The classifier pulls reviewed examples from Supabase, trains on them, and saves the model to SQLite (`app_kv` table).  Minimum examples threshold: `MIN_TRAINING_EXAMPLES = 10`.

## Step 5: Verify the classifier

```http
GET /api/training/status
```

Returns classifier version, accuracy, training timestamp, and example counts.

## What data is used for labeling

The pipeline uses **heuristic analysis** (`outlook_dashboard/ai.py:heuristic_analysis`).  It reads:

- Email subject and body for urgency keywords (URGENT, CEO, accessibility, legal, etc.)
- Importance flag from Outlook
- Sender domain
- Thread history (latest-message extraction strips quoted replies)

It does NOT call any external AI API from inside the running app. Default labels are deterministic given the email content. Agent-assisted labels are only produced by Codex/Claude when Brian explicitly asks an agent to train the model.

The internal response signals used for owner detection:

- Whether a reservations@ / frontdesk@ / management@ address appears in the thread
- Reply speed indicators in the subject / body if present
- How the internal staff member signed off

## Where things live

| Concern | Location |
|---|---|
| Import from Outlook | `outlook_dashboard/completed_requests_importer.py` |
| Full pipeline (import+label+upload+purge) | `outlook_dashboard/completed_training_pipeline.py` |
| Raw email pipeline (from local SQLite) | `outlook_dashboard/training_pipeline.py` |
| Heuristic labeling | `outlook_dashboard/ai.py:heuristic_analysis()` |
| Redaction | `outlook_dashboard/redaction.py:redact_sensitive_text()` |
| Local classifier training | `outlook_dashboard/local_classifier.py:train()` |
| Supabase upload | `outlook_dashboard/training_pipeline.py:_upload_example()` |
| Audit log | `completed_requests_log` table in SQLite |
| Training examples (cloud) | `training_examples` table in Supabase |

## Purge behavior

`purge_processed_training_emails()` is called automatically at the end of `run_completed_pipeline()`.  It:

- Deletes all rows from `emails` WHERE `source = 'completed_requests'` (cascade-deletes `email_analysis`)
- Deletes any `.msg` files under `data/outlook_exports/`
- Does NOT touch `completed_requests_log` (audit trail is preserved)
- Does NOT touch Supabase (uploaded training examples are preserved)

Live triage emails (`status = 'New'`) are never touched — the WHERE clause filters by source, not status.

## Troubleshooting

| Symptom | Check |
|---|---|
| `imported: 0` | Outlook COM not available (Windows only); or folder name wrong |
| `uploaded: 0, labeled > 0` | `SUPABASE_SERVICE_ROLE_KEY` not configured in `.env` |
| `failed > 0` | Check `completed_requests_log` result column and runtime log |
| `purged_email_rows: 0` | Emails were already purged, or none were imported |
| Classifier accuracy low | Review rejected/unlabeled examples in Supabase before retraining |

## Related docs

- `docs/TRAINING_PIPELINE.md` — privacy contract and Supabase schema details
- `docs/CLASSIFIER.md` — local classifier behavior, rollback, feature importance
- `docs/PROPERTY_KNOWLEDGE.md` — property-specific knowledge items that inform labeling
- `AGENTS.md` — full agent constraints and security rules
