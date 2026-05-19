# ReplyRight Architecture

ReplyRight is a local-first, read-only Outlook email triage dashboard for Waldorf Astoria New York reservations work. It ranks emails by urgency, assigns task ownership, summarizes threads, lists internal next steps, flags risk, collects feedback, and generates AI response suggestions only when the user explicitly asks.

## Active Application

The current runnable app is the Python/FastAPI dashboard in `outlook_dashboard/`, launched by `run_desktop.py` or packaged with `build_exe.ps1`.

```text
run_desktop.py
  -> starts FastAPI on 127.0.0.1:8000 by default
  -> opens a pywebview / WebView2 desktop window

outlook_dashboard/
  main.py              FastAPI routes, auth middleware, admin endpoints, lifecycle
  config.py            env loading, bundled secret injection, runtime paths
  database.py          SQLite schema, migrations, persistence helpers
  auth.py              Supabase Auth login/session/admin helper functions
  graph.py             optional Microsoft Graph OAuth/read-only sync
  outlook_desktop.py   read-only Outlook desktop COM import plus macro fallback
  ai.py                refresh triage, local classifier hook, AI fallback, reply analysis
  taxonomy.py          active categories, priorities, risks, statuses, owners
  taxonomy_meta.py     SLA, colors, descriptions, owner metadata, risk overrides
  signal_extractor.py  deterministic hotel signal extraction
  hotel_entities.py    pure hotel entity extraction used by heuristic triage
  travel_programs.py   pure luxury travel program detector used by heuristic triage
  urgency_engine.py    pure arrival-window urgency engine used by heuristic triage
  local_classifier.py  scikit-learn classifier training/prediction from Supabase examples
  sender_intelligence.py per-domain profile builder from Supabase feedback events
  training_pipeline.py redacted training example export to Supabase
  redaction.py         payment-like and identifier redaction
  supabase_client.py   feedback/rule/prompt/sender Supabase helpers and local cache
  kyc/                 KYC inspection settings, reminders, actions, history, audit API
  updater.py           GitHub release update check
  platform_compat.py   Windows/COM/webview capability flags
  runtime_log.py       shared logger factory
  static/              dashboard HTML/CSS/JS, branding, VBA macro
```

The `app/` directory is a Next.js/Prisma scaffold from an earlier production direction. It is not the current executable path. Keep it intact unless a migration is requested.

The `replyright_kernel/` package is an experimental Semantic Kernel layer. It is additive and not currently wired into the FastAPI desktop runtime.

Older root-level planning files are historical unless `docs/CURRENT_STATE.md` says otherwise.

## Runtime Shape

```text
PyInstaller ReplyRight.exe
  -> run_desktop.py
  -> FastAPI app in outlook_dashboard/main.py
  -> pywebview desktop shell
  -> local dashboard at http://127.0.0.1:8000
  -> SQLite runtime DB under data/
  -> optional Outlook COM, Microsoft Graph, Supabase, OpenAI, Google AI, Claude
```

The app is designed to remain useful when optional network integrations are unavailable.

## Data Flow

1. User signs in through Supabase Auth-backed ReplyRight login.
2. User clicks Refresh Inbox.
3. FastAPI calls the Outlook desktop importer.
4. The importer reads only `NYCWA_Reservations > Inbox` through read-only classic Outlook COM automation when available.
5. If COM dependencies are unavailable, the legacy Outlook VBA macro path can be launched as a fallback.
6. Imported messages are normalized and upserted into local SQLite.
7. After a successful Outlook refresh, local email rows whose message IDs were not present in the current import are deleted. This keeps local SQLite aligned to the Outlook inbox without mutating Outlook.
8. `triage_email()` attempts local classifier prediction when a model is available.
9. The deterministic hotel triage path remains the fallback and test baseline.
10. Shared Supabase rules and known sender mappings can adjust local analysis.
11. Refresh classification may call OpenAI when configured; if OpenAI is unavailable and Google AI is configured, it may call Google AI. If neither is available, local deterministic triage remains active.
12. The dashboard fetches `/api/emails`, groups rows by `conversation_id`, and renders queue/detail views.
13. User feedback is saved locally, uploaded to Supabase when configured, and queued locally for retry on upload failure.
14. Admin tools can export completed, redacted examples to Supabase training tables and train a local classifier from reviewed examples.

## Integrated Operations Modules

ReplyRight can host hotel operations modules alongside the reservations email assistant when they follow the same local-first, authenticated, audited architecture.

- KYC Inspections: `outlook_dashboard/kyc/` stores reminder settings, current due status, inspection events, acknowledge/snooze/complete/skip actions, and local/Supabase-mirrored history. It does not store KYC passwords, browser cookies, raw automation diagnostics, or Outlook content.
- Future possible modules: shift checklist, VIP arrival tracker, billing follow-up tracker, no-show/group audit tracker.

KYC Auto is being absorbed as a ReplyRight module rather than launched as a separate desktop app. The reusable behavior is the reminder cadence, active operator/team-member state, completion tracking, and login-error/status concepts. The legacy Tkinter UI and standalone installer are not part of the integrated runtime.

## Outlook Safety Boundary

ReplyRight intentionally does not send, delete, archive, move, categorize, mark read, or otherwise mutate Outlook messages.

Allowed Outlook behavior:

- Read from the configured shared mailbox/folder.
- Save local `.msg` copies under the ignored app data export folder.
- Store imported content in local SQLite.
- Delete stale local SQLite rows after a successful import.

Disallowed without a new explicit design:

- Sending replies
- Moving or archiving messages
- Deleting Outlook messages
- Marking messages read/unread
- Adding categories or flags in Outlook
- Modifying reservations or billing systems

## Authentication

Dashboard login prefers Supabase Auth when configured. `auth.py` uses Supabase `/auth/v1/*` endpoints for password login, token refresh, logout, admin provisioning, user invite/delete, and password reset support.

The `rr_session` cookie stores access and refresh tokens in an HttpOnly cookie. `_AuthMiddleware` validates or refreshes the token for protected routes.

For local-first continuity, `auth.py` also supports local SQLite users and sessions as a fallback when Supabase auth is unavailable or unconfigured. Local `users` rows from earlier installs remain valid, local session IDs can be stored in the same `rr_session` cookie, and first-run setup can create a local admin without asking for API keys.

## Persistence

SQLite is local by default:

```text
data/hotel_email_triage.sqlite3
```

Important local tables include:

- `emails`
- `email_analysis`
- `triage_feedback`
- `oauth_tokens`
- `oauth_states`
- `sync_runs`
- `rule_candidates`
- `supabase_rule_cache`
- `supabase_feedback_queue`
- `supabase_prompt_cache`
- `supabase_known_sender_cache`
- `training_pipeline_log`
- `audit_logs`
- `kyc_settings`
- `kyc_inspection_events`
- `kyc_acknowledgements`
- `kyc_audit_log`
- `app_kv`

The `data/` directory is intentionally ignored because it can contain mailbox content, local tokens, exports, model blobs, and logs.

Supabase tables are defined in `docs/supabase_schema.sql`:

- `feedback_events`
- `classification_rules`
- `known_senders`
- `prompt_versions`
- `training_examples`

`training_examples` is service-role only. The app must never print the service-role key.

## Intelligence Layers

### Deterministic Triage

`ai.py` contains the current deterministic hotel triage logic, latest-message cleanup, local classifier hook, OpenAI/Google refresh classification, Claude single-email analysis, shared-rule application, and fallback behavior.

This remains the baseline for tests and no-key operation.

### Signal Extraction

`signal_extractor.py` extracts named, explainable zero-API signals that can feed the classifier, admin inspector, urgency logic, and future staged pipeline.

### Hotel Entities

`hotel_entities.py` extracts confirmation numbers, arrival/departure dates, nights, room categories, rate codes, guest counts, arrival windows, and billing amounts. It supports English plus selected Spanish, French, Portuguese, Italian, and German hotel workflow terms.

It is pure and called by `heuristic_analysis()` during triage.

### Travel Programs

`travel_programs.py` detects luxury travel and internal programs from sender domains and body/signature keywords.

It is pure and called by `heuristic_analysis()` during triage.

### Urgency Engine

`urgency_engine.py` computes a deterministic urgency score and reason string from extracted entities, program data, category hints, and risk flags.

It is pure and called by `heuristic_analysis()` during triage.

### Local Classifier

`local_classifier.py` trains scikit-learn TF-IDF plus calibrated LogisticRegression pipelines for urgency, owner, and category. It downloads human-reviewed rows from Supabase `training_examples`, stores model bundles and metadata in local SQLite `app_kv`, retains the previous model blob, and exposes prediction, metadata, and feature importance helpers.

### Sender Intelligence

`sender_intelligence.py` rebuilds per-domain profiles from Supabase `feedback_events`. It tracks typical owner/category/urgency patterns, correction rate, and confidence. Sender intelligence should guide decisions conservatively.

### Shared Rules And Prompt Versions

`supabase_client.py` downloads approved rules, active prompt versions, and known sender mappings on startup. They are cached durably in SQLite so ReplyRight can use the last-known configuration while offline.

### External AI

Refresh Inbox:

- OpenAI first when `OPENAI_API_KEY` is configured.
- Google AI fallback when OpenAI is unavailable and `GOOGLE_AI_API_KEY` is configured.
- Local deterministic fallback when external AI is unavailable or errors.

Single-email Analyze/AI Suggestion:

- Claude/Anthropic only, when configured.
- If Claude is unavailable, the UI should show a clear error/fallback state rather than treating refresh OpenAI as the same feature.

Training refinement:

- The default pipeline is zero-credit and uses existing analysis labels.
- `refine=true` may call Claude for heuristic-only completed emails and must remain admin-explicit.

## Training Pipeline

`training_pipeline.py` creates privacy-preserving training records:

```text
completed local email
  -> latest-message cleanup
  -> redact_sensitive_text()
  -> subject tokenization
  -> label mapping from existing analysis
  -> optional Claude refinement only when refine=True
  -> Supabase training_examples upload with service-role key
  -> training_pipeline_log entry in SQLite
```

The pipeline stores `body_redacted`, sender domain, subject tokens, labels, engine metadata, and review flags. It must not store raw email bodies, full subjects, sender email addresses, payment details, or unredacted identifiers in Supabase.

## Admin Dashboard

Admin tools currently cover:

- Users and auth actions
- Suggested rules
- Prompt versions
- Training pipeline run/status
- Human review queue for training examples
- Local classifier train/status/feature importance
- Supabase-backed shared learning visibility

Admin actions should remain protected and auditable.

## Build And Packaging

`build_exe.ps1` packages `run_desktop.py` with PyInstaller, embeds the ReplyRight icon, collects project modules and important dynamic dependencies, and attempts to create Desktop and Start Menu shortcuts.

Important bundled/dynamic dependency areas:

- `outlook_dashboard`
- `pythonnet`, `clr`, `pywin32`, `win32com`
- `anthropic`
- `sklearn`, `scikit_learn`, `dateparser`, `joblib`, `threadpoolctl`

Ignored build/runtime folders include `.vendor/`, `.build-tmp/`, `build/`, `dist/`, `data/`, `.venv/`, and local temp folders.

## Current Constraints

- ReplyRight is single-property for Waldorf Astoria New York / `NYCWA_Reservations`.
- Multi-property and cross-property support are out of scope unless Brian explicitly reopens that direction.
- The inactive Next.js scaffold should stay inactive.
- The Semantic Kernel layer should stay optional.
- Reply sending is out of scope.
- Raw mailbox content must not be logged or committed.
