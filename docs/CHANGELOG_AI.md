# AI Change Log

## 2026-05-16 — Standalone window + Outlook detection

- Replaced Edge app-mode subprocess (`msedge.exe --app`) with `pywebview` / WebView2 embedded window. Window is now fully standalone: own process, own taskbar entry, no browser chrome.
- Fixed Edge process-handoff bug: Edge launcher was exiting immediately when Edge was already running, causing FastAPI server shutdown and "failed to fetch" on all buttons.
- Added runtime diagnostics log (`data/replyright-runtime.log`): rotating file handler, logs all HTTP requests with method/path/status/timing, Outlook export events, and AI analyze calls. Never logs email content.
- Fixed Outlook macro launch: now performs a thorough process search first; if Outlook is already open connects via COM and runs the macro in-place; only starts a new Outlook instance if none is found.
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
