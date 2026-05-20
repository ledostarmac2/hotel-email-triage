# AI Change Log

## 2026-05-20 - Zero-credit training pipeline guardrail

- Removed in-app Claude/Anthropic calls from the Completed Requests training pipeline.
- Kept `refine=true` as a backwards-compatible training API flag, but it no longer triggers Claude labeling.
- Completed Requests import now uses local heuristic labels, redacts/compacts examples, uploads to Supabase, and reports `external_ai_used=false`.
- Added regression coverage so training remains zero-credit even when Anthropic credentials exist.

## 2026-05-19 - KYC operations backend integration

- Added `outlook_dashboard/kyc/` as the backend foundation for an integrated KYC Inspections module.
- Added KYC settings, reminder status, event creation, acknowledge, snooze, complete, skip, and history APIs.
- Added local SQLite KYC tables plus best-effort Supabase mirroring for non-secret settings and event history.
- Added audit logging for KYC settings and event actions.
- Preserved KYC Auto's reminder/status concepts without importing its standalone Tkinter UI or Selenium automation into the active ReplyRight backend.

## 2026-05-19 - Release/auth safety repair

- Removed the user-facing credentials setup page and API endpoint path so the desktop app no longer asks users to paste API keys.
- Kept AI provider use configuration-driven: Refresh Inbox still uses OpenAI, then Google AI, then local deterministic fallback based on deployed environment values.
- Kept Claude/Anthropic reserved for explicit single-email Analyze/AI Suggestion behavior.

## 2026-05-18 - Multilingual hotel workflow bug tests

- Added multilingual reservation workflow tests for Spanish, French, Portuguese, Italian, and German hotel emails.
- Expanded deterministic hotel entity extraction for localized confirmation/reservation labels, arrival/departure terms, guest counts, night counts, date phrases, and presidential-suite mentions.
- Expanded training redaction so localized confirmation-number labels are sanitized before training examples are built.
- Expanded arrival-window urgency keywords for common localized billing, complaint, cancellation, thank-you, accessibility, allergy, and actionable request language.

## 2026-05-18 - Phase 7 hotel domain intelligence layer

- Added pure hotel entity extraction for confirmation numbers, stay dates, nights, room category, rate code, guest counts, arrival window, and mentioned billing amounts.
- Added luxury travel-program detection for Virtuoso, FHR, STARS, Signature, Mr_and_Mrs_Smith, Impresario, Hyatt_Prive, FS_Preferred, and internal Hilton senders.
- Added deterministic arrival-window urgency scoring from extracted entities and detected program metadata.
- Kept all three modules unwired from `triage_email()` so the operator can merge this branch with the parallel labeling branch before integration.
- Recorded `dateparser` in `new_dependencies.txt` instead of editing the parallel-agent-owned `requirements.txt`.

## 2026-05-17 - Phases 1-4 implementation pass

- Changed refresh triage so `triage_email()` attempts OpenAI classification when configured, with local deterministic triage as the fallback.
- Updated dashboard `OPENAI_MODEL` default to `gpt-5.4-nano` after checking official OpenAI docs for low-cost classification/extraction suitability.
- Added optional Google AI Studio/Gemini refresh-classification fallback through `GOOGLE_AI_API_KEY` / `GOOGLE_AI_MODEL`.
- Added a safe local setup script, `scripts/configure_google_ai_studio.ps1`, that prompts for a rotated Google AI Studio key and writes it to ignored `.env` without printing it.
- Added Google AI Studio configuration status to `/api/health`, `/api/config`, and the Admin AI Configuration card.
- Expanded structured feedback controls to include category, contact type, sentiment, status, and 1-5 summary/reply quality ratings.
- Added local SQLite columns for feedback status and quality ratings, and included those fields in Supabase `feedback_events`.
- Added durable local caching for approved Supabase rules and a retry queue for failed feedback uploads.
- Added durable local caching and startup sync for Supabase prompt versions and known sender mappings.
- Applied known sender mappings during local triage so sender-domain knowledge can correct owner/contact type without an external AI call.
- Adjusted rule learning thresholds: three matching corrections create visible candidates; five or more corrections are marked as auto-promoted/approved for shared learning.
- Added Admin Suggested Rules `Reject` and `Dismiss` controls for emergency override of bad rule candidates.
- Added `tests/test_import_smoke.py` and edge regressions for known sender cache, prompt cache, and rule-candidate dismissal.
- Updated `docs/supabase_schema.sql` with feedback rating/status fields and safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for existing Supabase projects.
- Updated `docs/supabase_schema.sql` with a `prompt_versions` table and active-prompt read policy.

## 2026-05-17 - Phase 7 local model training roadmap

- Expanded `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` with a full Phase 7 plan for local hotel-specific model training.
- Added the hybrid learning architecture: rules, Supabase feedback, sanitized historical examples, embeddings, lightweight local classifiers, and optional external AI fallback.
- Documented Phase 7 subphases from historical import/redaction through AI-assisted labeling, human review, classifier training, runtime prediction, continuous learning, and optional local LLM support.
- Added Supabase table targets for `training_emails`, `training_labels`, `model_versions`, `model_metrics`, `prediction_logs`, and `human_review_queue`.
- Updated `docs/ARCHITECTURE.md`, `docs/CURRENT_STATE.md`, and `docs/DECISIONS.md` to make privacy-preserving local classifier training part of the long-term ReplyRight direction.

## 2026-05-16 - Roadmap audit handoff

- Recorded a seven-phase roadmap completion checklist in `docs/HANDOFF.md`.
- Marked next implementation blanks: structured feedback controls, 1-5 quality ratings, Supabase durable sync/cache, hands-off rule auto-promotion, and staged OpenAI refresh classification.
- Recorded Brian's decisions: OpenAI classifies all imported mail on refresh; Claude Opus is only for `AI Suggestion`; shared rules auto-promote; multi-property support is out of scope.
- Updated `docs/CURRENT_STATE.md` so future agents begin with those gaps.

## 2026-05-16 - Admin tab navigation restore

- Fixed Admin view state so it no longer strands the app on the admin dashboard after clicking other sidebar tabs.
- Added a restorable/re-bindable inbox workspace shell for the queue and detail panels.
- Hid `Refresh Inbox` and inbox metrics while Admin is active, then restored them when returning to inbox views.
- Replaced the admin CSS `:has()` dependency with an explicit `.workspace--admin` class.
- Rebuilt `dist\ReplyRight.exe` and verified Admin -> Inbox -> Urgent with a headless Edge/Selenium pass.

## 2026-05-16 - Login feedback and admin credential repair

- Moved local admin credential seeding to `.env` variables and made startup repair stale admin password hashes.
- Updated failed login handling so invalid credentials render a persistent dismissable error message and preserve the email field.
- Updated dashboard failure toasts to persist until dismissed with an X.
- Fixed the auth middleware skip list so `/api/auth/me` is protected and can receive `request.state.user`; this resolves the post-login dashboard boot loop.
- Rebuilt the packaged EXE and verified bad/good login behavior against the packaged app.

## 2026-05-16 - Adaptive conversation triage and Supabase roadmap

- Added conversation-level adaptive triage so queue urgency/labels come from the latest few messages instead of the highest stale score anywhere in the thread.
- Added latest-message cleanup to reduce false upset sentiment from quoted Outlook history.
- Added local `triage_feedback` persistence plus `POST /api/emails/{email_id}/feedback` for per-conversation correction notes.
- Added a compact feedback box in the detail pane with optional urgency and owner corrections.
- Added local learning behavior for completed CCA/payment-form patterns: route to Reservations, summarize the actual action, and avoid false urgent/VIP/concierge labels.
- Fixed the main shell scrolling model so the message queue scrolls independently and the detail pane resets to the top when selecting a thread.
- Rebuilt `dist\ReplyRight.exe`; packaged health check succeeded with 28 conversation groups and urgency distribution `2:14, 3:4, 4:7, 5:3`.
- Added `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` as the broader architecture roadmap for Supabase shared learning, staged AI classification, rule candidates, and admin review.

## 2026-05-16 - Outlook source-of-truth and hotel triage rules

- Removed dashboard mock/demo seeding from the active app path, including the mock seed route and mock data fixture module.
- Refresh Inbox now deletes local email rows not present in the current Outlook import; packaged verification deleted 6 stale/non-current rows.
- Inbox list now groups by Outlook `conversation_id`; final packaged verification rendered 46 imported Outlook emails as 28 conversation groups.
- Added contact classification: Internal, Group contact, Travel agency, Direct guest.
- Restricted department owners to operating departments only: Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, All Departments.
- Reworked urgency scoring around parsed arrival/check-in date, with upset sentiment able to raise urgency.

## 2026-05-16 - Refresh Inbox direct Outlook import

- Replaced the Outlook refresh PowerShell/VBScript macro trigger with direct read-only `pywin32` COM import.
- Refresh Inbox now reads only `NYCWA_Reservations > Inbox`, saves local `.msg` copies, imports messages into SQLite in-process, and runs local triage immediately.
- Kept `outlook.exe /autorun` as a legacy fallback if `pywin32` is unavailable.
- Added `pywin32>=306` to requirements and build vendoring, with PyInstaller hidden imports for `pythoncom`, `pywintypes`, and `win32com.client`.
- Verified the packaged EXE endpoint imported 44 messages, analyzed 44, skipped 0, and used `launch_method=pywin32-com`.

## 2026-05-16 — Standalone window + Outlook detection

- Replaced Edge app-mode subprocess (`msedge.exe --app`) with `pywebview` / WebView2 embedded window. Window is now fully standalone: own process, own taskbar entry, no browser chrome.
- Fixed Edge process-handoff bug: Edge launcher was exiting immediately when Edge was already running, causing FastAPI server shutdown and "failed to fetch" on all buttons.
- Added runtime diagnostics log (`data/replyright-runtime.log`): rotating file handler, logs all HTTP requests with method/path/status/timing, Outlook export events, and AI analyze calls. Never logs email content.
- Reworked Outlook process detection during launcher experiments; this was later superseded by the direct read-only `pywin32` import path above.
- Added `pywebview>=4.4,<6` to requirements.txt and build_exe.ps1 (with `--collect-all webview` and hidden-import flags for edgechromium/winforms backends).
- Updated DECISIONS.md with two new architecture decisions.

## 2026-05-16 — Semantic Kernel orchestration layer

- Created `replyright_kernel/` package: settings, engine factory, plugin registry, and demo pipeline.
- Implemented three native SK plugins: PriorityTriagePlugin (urgency scoring, 20+ local rules), ExecutiveSummaryPlugin (HTML strip, quoted-thread removal, token budget enforcement), AuditCompliancePlugin (8-rule compliance gate covering guarantees, fault admissions, payment leakage, legal/medical/discrimination risk, unapproved promises).
- Registered all plugins into the SK kernel workspace with labelled extension points for future Graph and CRM plugins.
- Built a four-step async demo pipeline (clean → triage → LLM draft → audit) runnable via `python -m replyright_kernel.demo`.
- Added 59 unit and integration tests (mocked LLM, no API credits). All pass alongside the existing 2 dashboard tests.
- Updated requirements.txt with `semantic-kernel>=1.15,<2`; updated `.env.example` with `KERNEL_LOG_LEVEL`.
- Updated CURRENT_STATE.md, HANDOFF.md, DECISIONS.md per AGENTS.md protocol.

## 2026-05-16

- Created the multi-agent handoff documentation framework.
- Documented the active ReplyRight desktop architecture and current operational status.
- Added durable future-agent rules in `AGENTS.md`.
- Captured key decisions around read-only Outlook access, VBA ingestion, local triage, on-demand AI, SQLite, and Edge app mode.
- Cleaned up build/macro portability notes so future work can resume from another machine.

## Earlier Project History

- Scaffolded an initial Next.js/Prisma reservations triage app under `app/`.
- Added reference project snapshots under `reference/`.
- Added the Python/FastAPI Outlook email intelligence dashboard under `outlook_dashboard/`.
- Rebranded the executable/dashboard work to ReplyRight and added provided icon/logo assets.
