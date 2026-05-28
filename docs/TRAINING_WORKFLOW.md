# Training the Classifier - Agent Runbook

Last updated: 2026-05-28

## What This Document Is

This is the authoritative workflow for any agent asked to "train the model" or "train the classifier."

There are two separate training paths. Do not merge them.

## Path A: In-App Zero-Credit Pipeline

The running app and FastAPI/admin training endpoints must remain zero-credit.

They may:

- Import completed local emails or read the Outlook `Completed Request` folder.
- Run deterministic/local heuristic labels as staging labels.
- Redact and compact examples.
- Upload sanitized examples to Supabase with `human_reviewed=false`.
- Train only from examples already marked reviewed.

They must not:

- Call Claude, OpenAI, Google AI, or any external model during Refresh Inbox.
- Call Claude, OpenAI, Google AI, or any external model from in-app training endpoints.
- Treat heuristic labels as final agent-reviewed labels.

`run_completed_pipeline()` belongs to this path. By itself, it does not satisfy Brian's outside-agent request to train the classifier because it uses `heuristic_analysis()` as the labeler. Heuristics are not the final labeler for outside-agent training.

## Path B: Outside-Agent Assisted Training

When Brian explicitly tells Codex or Claude to "train the model" or "train the classifier," use this path.

Correct interpretation of "you classify": the outside agent labels sanitized examples using its own model judgment, then trains the local classifier from those agent-reviewed labels. The app runtime still never calls external AI from Refresh Inbox or training endpoints.

Required steps:

1. Import Completed Request emails that have not already been imported for training.
2. Preserve duplicate-prevention metadata, such as stable fingerprints and `completed_requests_log` entries, so future runs skip already-imported messages.
3. Redact and sanitize imported content before labeling.
4. Use only safe labeling inputs:
   - redacted body excerpt
   - sender domain only, not full sender email
   - safe subject tokens, not raw PII-heavy subjects
   - safe extracted metadata
   - stable fingerprint/import ledger key
5. The outside agent labels the sanitized examples using its own model judgment.
6. Labels must include at minimum:
   - urgency
   - owner
   - category
7. If the current training store/classifier supports them, also label:
   - contact type
   - risk flags
   - status/no-action
   - recommended action
8. Store only sanitized labeled training examples.
9. Train `outlook_dashboard.local_classifier` from agent-labeled/reviewed examples.
10. Purge raw imported Completed Request bodies.
11. Keep safe fingerprints/import ledger data so future runs skip already-imported items.
12. Verify classifier status, version, metrics, targets, warnings, and class imbalance.

## What Is Wrong

If a handoff or script says "`run_completed_pipeline()` plus `train()` does exactly this," treat that as wrong unless there is a separate outside-agent labeling step where sanitized examples are actually labeled by Codex/Claude model judgment.

Wrong for Brian's outside-agent request:

- Calling only `run_completed_pipeline(...)`.
- Using `heuristic_analysis(...)` as the labeling authority.
- Letting the deterministic engine label examples and calling the job done.
- Calling the app's training API and assuming the model was agent-trained.

Allowed as reference/staging only:

- Heuristic labels.
- Existing local classifier guesses.
- Deterministic rule outputs.

The final agent-assisted labels must come from the outside agent reviewing sanitized examples.

## Privacy and Safety Invariants

- Raw `body_text` is never uploaded. Only redacted body excerpts or `body_redacted` may be stored.
- Full sender email is never stored. Only `sender_domain`.
- Full subject is never stored. Only `subject_tokens`.
- Raw Outlook EntryIDs/message IDs are never stored in Supabase or label files; keep import ledger data local.
- Reservation numbers, payment identifiers, card data, confirmation numbers, attachments, session cookies, and service-role keys must not appear in Supabase, docs, logs, or final responses.
- Outlook is read-only: do not send, delete, archive, move, categorize, flag, or mark messages read/unread.
- Redaction must not be weakened.

## Current Tooling

`scripts/agent_label_completed_requests.py` is the intended outside-agent helper once reviewed. Its shape is:

1. `--import`: read unimported Completed Request messages, emit sanitized pending examples, and write duplicate-prevention ledger entries.
2. Outside agent: read the sanitized pending examples and create a labeled JSON file using model judgment.
3. `--upload`: upload sanitized labeled examples, train the classifier, and purge transient raw imports.

If using another workflow, it must meet the same contract.

## Verification Checklist

When reviewing Claude's work or your own training pass, check:

- Did the agent actually label sanitized examples using agent/model judgment?
- Or did it incorrectly use `heuristic_analysis()` / `run_completed_pipeline()` as the final labeler?
- Are runtime training endpoints still zero-credit?
- Are raw imported bodies purged after labeling/training?
- Is duplicate-prevention metadata retained?
- Are only sanitized examples stored?
- Are tests proving these boundaries?

## In-App Pipeline Reference

The zero-credit pipeline remains useful for staging unreviewed examples:

```python
from outlook_dashboard.completed_training_pipeline import run_completed_pipeline

result = run_completed_pipeline(
    mailbox_name="NYCWA_Reservations",
    folder_name="Completed Request",
    batch_size=1000,
)
```

Use this only as the in-app/sanitized-import path. It is not the outside-agent labeling authority.

## Classifier Training Reference

After reviewed labels exist:

```python
from outlook_dashboard.local_classifier import train, get_classifier_status

result = train()
status = get_classifier_status()
```

Report aggregate counts and metrics only: imported/labeled/uploaded/skipped/failed/purged, classifier version, examples, target accuracies, warnings, and class imbalance.

## Related Docs

- `docs/TRAINING_PIPELINE.md` - privacy contract and Supabase schema details.
- `docs/CLASSIFIER.md` - local classifier behavior, rollback, feature importance.
- `docs/PROPERTY_KNOWLEDGE.md` - property-specific knowledge items that inform labeling.
- `AGENTS.md` - agent constraints and security rules.
