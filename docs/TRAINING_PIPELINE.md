# Training Pipeline

Last updated: 2026-05-28

## Purpose

ReplyRight's training pipeline turns completed emails into privacy-preserving, staged training examples for review and local classifier training.

The in-app pipeline is zero-credit. It uses local heuristic or existing `email_analysis` labels as staging labels, redacts and compacts the latest message, uploads sanitized records to Supabase, and leaves human/agent review as the quality gate.

When Brian explicitly asks an outside agent to "train the model" or "train the classifier," that outside agent must label sanitized examples using its own model judgment. The app's deterministic heuristic labels can be a reference signal, but they are not the final labeler for Brian's agent-assisted training workflow.

## Runtime Components

- `outlook_dashboard/training_pipeline.py` exports completed local email rows.
- `outlook_dashboard/completed_requests_importer.py` reads Outlook `"Completed Request"` through read-only COM.
- `outlook_dashboard/completed_training_pipeline.py` imports completed requests, applies heuristic staging labels, and uploads sanitized examples.
- `outlook_dashboard/redaction.py` removes payment-like and sensitive identifiers.
- `outlook_dashboard/local_classifier.py` trains from human-reviewed Supabase examples.

## Data Flow

```text
Completed local email or Completed Request folder
  -> latest-message cleanup
  -> local heuristic/existing analysis labels as staging labels
  -> redact_sensitive_text()
  -> compact subject tokens + body_redacted
  -> upload to Supabase training_examples with service-role key, usually unreviewed
  -> human review or outside-agent labeling/review on sanitized examples
  -> train local classifier from reviewed examples
```

ReplyRight training endpoints do not call Claude/Anthropic, OpenAI, or Google AI.
Heuristic staging does not equal agent-reviewed training.

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
- `label_recommended_action`
- `label_missing_info`
- `label_reply_required`
- `label_escalation_required`
- `labeling_engine`
- `human_reviewed`
- `app_version`

`training_examples` is service-role only. The publishable/anon key must not be able to read or write it.

## Admin Endpoints

- `POST /api/admin/training/run`
- `POST /api/admin/training/import-completed-requests`
- `GET /api/admin/training/status`
- `GET /api/admin/training/completed-requests/status`
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

Completed Request import:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/admin/training/import-completed-requests" -Method POST -WebSession $session -ContentType "application/json" -Body (@{
  mailbox_name = "NYCWA_Reservations"
  folder_name = "Completed Request"
  batch_size = 50
} | ConvertTo-Json)
```

Do not print passwords, cookies, or service-role keys.

## Agent-Assisted Review

Brian may use Codex or Claude outside the running app to inspect sanitized examples and produce labels. This is the required path when Brian tells an outside agent to "train the model" or "train the classifier."

Agent-assisted review means:

- The outside agent labels sanitized examples using model judgment.
- Safe inputs only: redacted body excerpt, sender domain, subject tokens, safe metadata, and stable fingerprint/import key.
- Required labels: urgency, owner, and category.
- Optional labels where supported: contact type, risk flags, status/no-action, and `recommended_action`.
- The reviewed labels are written back through the review/Supabase workflow or a reviewed agent-training helper.

It does not mean:

- Calling `run_completed_pipeline()` and stopping.
- Treating `heuristic_analysis()` labels as the final label authority.
- Calling the app's training endpoint and assuming agent-assisted training happened.

ReplyRight itself should not spend Anthropic/OpenAI/Google platform credits for training endpoints.

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
python -m pytest tests/test_training_pipeline.py tests/test_completed_training_pipeline.py tests/test_redaction.py -v
```

End-to-end packaged smoke checks:

1. Start `dist\ReplyRight\ReplyRight.exe` in the background.
2. Confirm `/api/health` returns `ok=true`.
3. Query packaged SQLite for `training_pipeline_log`.
4. Log in and post `/api/admin/training/run?batch_size=50`.
5. Query Supabase `training_examples?select=id&limit=5` using the service-role key without printing the key.

## Known Gaps

- Enough human-reviewed examples are required before the classifier can train.
- Broader historical import workflows remain future work beyond Completed Request.
- Agent-reviewed label import ergonomics can be improved.
