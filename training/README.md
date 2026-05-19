# Training Folder — ReplyRight Completed Requests Pipeline

This folder is shared between all agents (Claude and Codex) and contains:

- `README.md` — this file; describes how to trigger training
- `PROPERTY_KNOWLEDGE.md` — **auto-generated**; property-specific entities extracted from completed email examples

---

## What this pipeline does

The Completed Requests pipeline imports emails from the **"Completed Requests"** Outlook folder (a sub-folder of the shared reservations inbox) and:

1. Reads up to 50 emails per batch from that folder (read-only; never mutates Outlook)
2. Runs PII redaction on each email body
3. Calls **Claude Sonnet** (`claude-sonnet-4-6`) to extract:
   - **Training labels**: urgency (1–5), owner department, category, sentiment
   - **Property knowledge**: room types, rate plans, packages, offers, department routing patterns, inferred SOPs
4. Stores sanitized training examples in the local SQLite DB and uploads to Supabase `training_examples`
5. Persists property knowledge to `property_knowledge_items` in SQLite
6. Rebuilds `PROPERTY_KNOWLEDGE.md` from the accumulated knowledge

---

## How to trigger training

### Via the Admin API (preferred)

```http
POST /api/admin/training/import-completed-requests
Authorization: <session cookie>
Content-Type: application/json

{
  "mailbox_name": "Waldorf Reservations",
  "folder_name": "Completed Requests",
  "batch_size": 50
}
```

Response:
```json
{
  "imported": 47,
  "labeled": 45,
  "uploaded": 45,
  "knowledge_items": 182,
  "skipped": 2,
  "failed": 0,
  "folder": "Completed Requests",
  "mailbox": "Waldorf Reservations"
}
```

### Check status

```http
GET /api/admin/training/completed-requests/status
```

### Retrieve extracted property knowledge

```http
GET /api/admin/training/property-knowledge
GET /api/admin/training/property-knowledge?item_type=sop
GET /api/admin/training/property-knowledge?item_type=room_type
GET /api/admin/training/property-knowledge?item_type=rate_plan
```

---

## Existing pipeline (emails already imported to the inbox)

To process emails already imported to the main inbox with status=`Completed`:

```http
POST /api/admin/training/run?batch_size=10&refine=true
```

---

## Privacy contract

- Raw email bodies are **never** passed to Claude. Only `body_redacted` (output of `redact_sensitive_text()`).
- Full sender email addresses are **never** stored in training data. Only `sender_domain`.
- Full subjects are **never** stored. Only `subject_tokens` (stop-word-filtered keywords ≥4 chars).
- No reservation numbers, payment details, or guest names leave the local machine in raw form.

---

## Key source files

| File | Purpose |
|------|---------|
| `outlook_dashboard/completed_requests_importer.py` | Read-only Outlook COM importer for "Completed Requests" folder |
| `outlook_dashboard/property_knowledge.py` | Claude Sonnet extraction + persistence |
| `outlook_dashboard/completed_training_pipeline.py` | Orchestration: import → label → store → rebuild |
| `outlook_dashboard/training_pipeline.py` | Existing pipeline for inbox-imported emails |
| `outlook_dashboard/local_classifier.py` | TF-IDF + LogisticRegression local classifier |
| `training/PROPERTY_KNOWLEDGE.md` | Auto-generated property knowledge base |

---

## For agents: starting a training run

To start training the model, call the `run_completed_pipeline()` function in Python:

```python
from outlook_dashboard.completed_training_pipeline import run_completed_pipeline

result = run_completed_pipeline(
    mailbox_name="YOUR_MAILBOX_NAME",  # e.g. "Waldorf Reservations"
    folder_name="Completed Requests",
    batch_size=50,
)
print(result)
```

Or use the HTTP endpoint above if the FastAPI server is running.

> **Note for Codex**: The `completed_requests_log` table in SQLite tracks which Outlook EntryIDs have already been processed so the pipeline is safe to run repeatedly — it will only process new emails each time.
