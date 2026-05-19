# Training Pipeline

Last updated: 2026-05-18

## Purpose

ReplyRight's training pipeline turns completed local emails into privacy-preserving, labeled training examples for the local classifier.

The default pipeline is zero-credit. It uses labels already stored in local `email_analysis`. Claude refinement is optional, admin-explicit, and only applies to heuristic-only rows when `refine=true`.

## Runtime Components

- `outlook_dashboard/training_pipeline.py` builds and uploads sanitized training examples.
- `outlook_dashboard/redaction.py` removes payment-like and sensitive identifiers.
- `outlook_dashboard/database.py` lists eligible completed emails and writes `training_pipeline_log`.
- `outlook_dashboard/main.py` exposes admin endpoints.
- `docs/supabase_schema.sql` defines Supabase `training_examples`.
- `outlook_dashboard/local_classifier.py` trains from human-reviewed examples.

## Data Flow

```text
Completed local email
  -> list_unprocessed_completed_emails()
  -> latest_message_text()
  -> redact_sensitive_text()
  -> subject token extraction
  -> label mapping from existing email_analysis
  -> optional Claude refinement if refine=True
  -> upload to Supabase training_examples with service-role key
  -> log_training_example() in local SQLite
```

## Privacy Contract

Supabase `training_examples` must store only sanitized training data:

- `sender_domain`, not full sender email.
- `subject_tokens`, not full subject.
- `body_redacted`, never raw `body_text`.
- Label metadata such as urgency, owner, category, status, sentiment, missing info, reply required, and escalation required.
- `email_fingerprint`, not a raw message ID.

Do not store raw guest email bodies, full subjects, reservation numbers, payment details, attachments, session cookies, or service-role keys in Supabase or docs.

## Supabase Table

The active schema is in `docs/supabase_schema.sql`.

Important columns:

- `email_fingerprint`
- `sender_domain`
- `subject_tokens`
- `body_redacted`
- `label_urgency`
- `label_owner`
- `label_category`
- `label_status`
- `label_sentiment`
- `label_contact_type`
- `label_missing_info`
- `label_reply_required`
- `label_escalation_required`
- `labeling_engine`
- `human_reviewed`
- `app_version`

`training_examples` is service-role only. The publishable/anon key must not be able to read or write it.

## Admin Endpoints

Current admin endpoints include:

- `POST /api/admin/training/run`
- `GET /api/admin/training/status`
- `GET /api/admin/training/examples`
- `PATCH /api/admin/training/examples/{id}/review`
- `POST /api/admin/classifier/train`

Admin routes require an authenticated session.

## Running The Pipeline

From a running app session, the Admin UI can trigger the pipeline.

API smoke path:

```powershell
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-WebRequest -Uri http://127.0.0.1:8000/login -Method POST -WebSession $session -Body @{
  email = "<admin email>"
  password = "<admin password>"
}
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/admin/training/run?batch_size=50" -Method POST -WebSession $session
```

Do not print passwords, cookies, or service-role keys.

## Claude Refinement

`refine=false`:

- Uses existing labels.
- Zero AI credit usage.
- Default and preferred mode.

`refine=true`:

- May call Claude for heuristic-only emails.
- Must remain admin-explicit.
- Should only run on redacted/latest-message text.

Claude must not be called during bulk Refresh Inbox.

## Human Review

Training examples default to `human_reviewed=false`.

Classifier training downloads only human-reviewed examples. The admin review queue is the quality gate between raw training exports and model training.

Human review should prioritize:

- Low-confidence labels.
- Urgency 5 labels.
- Billing, legal, medical, ADA/accessibility, and chargeback cases.
- VIP and luxury travel program cases.
- Any category/owner combination that looks inconsistent.

## Verification

Targeted tests:

```powershell
python -m pytest tests/test_training_pipeline.py -v
python -m pytest tests/test_redaction.py -v
```

End-to-end packaged smoke checks:

1. Start `dist\ReplyRight\ReplyRight.exe` in the background.
2. Confirm `/api/health` returns `ok=true`.
3. Query packaged SQLite for `training_pipeline_log`.
4. Log in and post `/api/admin/training/run?batch_size=50`.
5. Query Supabase `training_examples?select=id&limit=5` using the service-role key without printing the key.

## Known Gaps

- Enough human-reviewed examples are required before the classifier can train.
- The pipeline currently exports from completed local email rows; broader historical import workflows remain future work.
- `dateparser` is now listed in the active dependency file.
