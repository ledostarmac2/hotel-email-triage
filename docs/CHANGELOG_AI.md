# AI Change Log

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
