# Training Folder - ReplyRight Completed Requests Pipeline

This folder is shared between agents such as Codex and Claude Code.

- `README.md` - this file
- `PROPERTY_KNOWLEDGE.md` - optional generated property knowledge notes

## What The In-App Pipeline Does

The Completed Requests pipeline imports emails from the Outlook "Completed Requests" folder and:

1. Reads a batch from that folder through read-only Outlook COM.
2. Runs local heuristic classification.
3. Redacts and compacts each latest-message body.
4. Stores sanitized training examples in Supabase `training_examples`.
5. Marks Outlook EntryIDs as processed in local SQLite so reruns skip old rows.

It does not call Claude, Anthropic, OpenAI, Google AI, or any other paid AI API.

## Agent-Assisted Grading

Brian may occasionally use Codex or Claude Code outside the running ReplyRight app to inspect sanitized examples, grade labels, and prepare reviewed training material. That work should be written back through the review/Supabase workflow. Do not wire ReplyRight itself to spend Anthropic platform credits for batch training.

## Admin API

```http
POST /api/admin/training/import-completed-requests
Content-Type: application/json

{
  "mailbox_name": "NYCWA_Reservations",
  "folder_name": "Completed Requests",
  "batch_size": 50
}
```

Response includes:

```json
{
  "imported": 47,
  "labeled": 47,
  "uploaded": 47,
  "knowledge_items": 0,
  "skipped": 0,
  "failed": 0,
  "external_ai_used": false,
  "labeling_mode": "heuristic"
}
```

## Other Endpoints

```http
GET /api/admin/training/completed-requests/status
GET /api/admin/training/property-knowledge
POST /api/admin/training/run?batch_size=10
```

`refine=true` is retained only for compatibility and does not call Claude.

## Privacy Contract

- Raw email bodies are not sent to external AI by the in-app training pipeline.
- Full sender email addresses are never stored in training data. Only `sender_domain`.
- Full subjects are never stored. Only `subject_tokens`.
- Supabase receives redacted latest-message text, labels, and metadata.

## Key Source Files

| File | Purpose |
| --- | --- |
| `outlook_dashboard/completed_requests_importer.py` | Read-only Outlook COM importer for "Completed Requests" |
| `outlook_dashboard/completed_training_pipeline.py` | Import, heuristic label, compact, upload |
| `outlook_dashboard/training_pipeline.py` | Existing completed local email export pipeline |
| `outlook_dashboard/local_classifier.py` | TF-IDF + LogisticRegression local classifier |
| `training/PROPERTY_KNOWLEDGE.md` | Optional generated property knowledge notes |
