# Current State

Last updated: 2026-05-16 (adaptive triage feedback and Supabase roadmap)

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked conversation queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and now uses read-only `pywin32` COM import as the primary path. The legacy `ExportNYCWAReservationsInboxOnly` VBA macro remains a fallback when direct import dependencies are unavailable.
- Bulk imports use local rules for speed. OpenAI is only called when a user requests an AI response for a selected email.
- Microsoft Graph OAuth code exists but is not the active path because the user hit enterprise access restrictions in Microsoft Entra.
- `build_exe.ps1` builds `dist\ReplyRight.exe` and attempts Desktop/Start Menu shortcuts. The latest source uses **pywebview** (WebView2/edgechromium backend) for the desktop window.
- The rebuilt `dist\ReplyRight.exe` was launch-tested by the user: the pywebview window opens, the dashboard loads, and the sidebar tabs work.
- Refresh Inbox was verified through the packaged EXE: it directly read/imported 46 messages from `NYCWA_Reservations > Inbox`, analyzed 46 locally, skipped 0, and did not launch the VBA macro (`launch_method=pywin32-com`). A prior verification pass deleted 6 stale/non-current rows.
- The inbox API now returns 28 conversation groups from those 46 Outlook emails. Conversation details include the thread messages for the selected conversation.
- Owner routing is limited to operating departments: Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, and All Departments. There is no Management owner.
- Local triage classifies contact type as Internal, Group contact, Travel agency, or Direct guest.
- Queue urgency is now computed at the conversation level from the latest few messages, rather than taking the highest score from stale messages in the thread.
- Latest-message sentiment ignores quoted Outlook history where possible, so old upset text does not override a friendly/completed latest reply.
- Local adaptive feedback is implemented:
  - `triage_feedback` stores per-conversation correction notes and optional corrected urgency/owner/category/contact/sentiment.
  - `POST /api/emails/{email_id}/feedback` applies feedback immediately to the selected conversation.
  - Similar future messages can reuse stored local feedback patterns.
- A CCA/completed-form pattern now routes to Reservations with concise steps to apply the form and confirm completion.
- Urgency is deliberately more conservative: level 5 is reserved for same/next-day operational blockers or serious risk, while completed/thank-you/form-submission updates are lowered unless a high-risk signal is present.
- `python -m unittest tests.test_ai_and_database` and `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` pass with the project-local temp workaround.
- `dist\ReplyRight.exe` was rebuilt after adaptive triage changes. Packaged health check succeeded, and current packaged data rendered 28 conversation groups with urgency distribution `2:14, 3:4, 4:7, 5:3`.
- `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` now captures the broader Supabase/shared-learning roadmap.

## Known Local Build/Launch Notes

- Desktop launcher uses **pywebview** (`webview.start(gui="edgechromium")`). WebView2 runtime ships with Windows 10/11 (22H2+) but must be present on any machine running the EXE.
- `run_desktop.py` does a pre-flight `import clr` check and raises a descriptive error if pythonnet is missing, rather than crashing natively with no log entry.
- Startup logging is in `run_desktop.py`; packaged builds write to `dist\data\replyright-startup.log`.
- `build_exe.ps1` auto-skips `.venv` and `.build-venv` to find system Python (VS Code auto-activates project venvs). If `.vendor` exists but is empty/partial, delete it and rebuild — the existence check short-circuits pip install.
- If Defender locks `dist\ReplyRight.exe` during a rebuild, the script falls back to renaming the old EXE to `.exe.old`. If both are locked, delete them manually first.
- Start Menu shortcut creation may fail on this locked-down Windows environment. Desktop shortcut creation uses the OneDrive Desktop path as a fallback.
- Local Python temp-directory permissions were unreliable. `build_support/sitecustomize.py` exists as a workaround for project-local dependency installation.
- Mock/demo data seeding has been removed from the active dashboard path.

## Config Requirements

Copy `.env.example` to `.env` for local runs. `.env` must not be committed.

Important variables:

- `OPENAI_API_KEY` for on-demand AI responses.
- `OPENAI_MODEL`, default `gpt-4.1-mini`.
- `APP_HOST=127.0.0.1`
- `APP_PORT=8000`
- `OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations`
- `OUTLOOK_EXPORT_FOLDER=Inbox`
- Optional Microsoft Graph values: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`, `MICROSOFT_REDIRECT_URI`, `SHARED_MAILBOX_EMAIL`.

## Current Risks

- The legacy VBA macro fallback must be installed manually only on machines where the direct `pywin32` import path is unavailable.
- The app must be running before Refresh Inbox; direct import happens in-process through the FastAPI endpoint.
- Outlook direct COM import depends on classic Outlook for Windows and bundled `pywin32`; if unavailable, ReplyRight falls back to the legacy `/autorun` VBA macro path.
- AI drafts are suggestions only and require human review.
- Local adaptive feedback is useful but not yet centralized. Feedback is currently stored only on the local machine until Supabase integration is implemented.
- This app intentionally does not mutate Outlook messages; adding send/archive/move/category actions requires a new design and approval.
- Local mailbox exports and SQLite data are ignored for privacy and are not portable through git.

## Semantic Kernel Orchestration Layer

A new `replyright_kernel/` Python package implements the foundational SK orchestration layer:

- **PriorityTriagePlugin** — local urgency scoring 1–5 (regex/keyword, no LLM cost)
- **ExecutiveSummaryPlugin** — strips HTML, quoted threads, signatures, legal footers, tracking noise; enforces 8 000-char token budget
- **AuditCompliancePlugin** — pre-display compliance scan; blocks guarantees, fault admissions, payment leakage, legal/medical/discrimination risk language, unapproved promises
- **engine.py / registry.py** — builds and registers the kernel; clearly labelled extension points for future Graph and CRM plugins
- **demo.py** — runnable four-step pipeline demo (`python -m replyright_kernel.demo`)

The layer is additive. It does not touch the existing FastAPI dashboard, Next.js scaffold, or Outlook read path.

Tests: `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` (59 tests, no API key required).

`OPENAI_MODEL` defaults to `gpt-5.5` in the kernel layer; the dashboard still uses `gpt-4.1-mini` unless overridden. `KERNEL_LOG_LEVEL` controls kernel log verbosity.

## Recommended Next Steps

1. **Claude immediate pickup**: launch the rebuilt Desktop shortcut, click Refresh Inbox once, and visually confirm the feedback box, resized window behavior, and Outlook-like independent scrolling.
2. **Claude immediate pickup**: spot-check real conversations that were formerly over-scored as urgency 4/5, especially completed CCA/payment form threads and friendly travel-agent replies.
3. **Claude immediate pickup**: if the UI looks right, record a real feedback note on one misclassified thread and confirm it relabels the conversation immediately.
3. **If launch fails**: inspect `dist\data\replyright-startup.log`. Look for `pythonnet (clr) is not available`; if seen, delete `.vendor` and re-run `.\build_exe.ps1` so pip re-installs pythonnet.
4. **Keep the macro available as fallback**: import `outlook_dashboard/static/outlook_refresh_macro.bas` into Outlook VBA (Alt+F11) only if the direct `pywin32` import path is unavailable on a target machine. Macro must be named `ExportNYCWAReservationsInboxOnly` or match `OUTLOOK_EXPORT_MACRO` in `.env`.
5. **Use the roadmap**: read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` before broad architecture work, especially Supabase shared learning, staged AI pipeline, and admin dashboard planning.
6. **Wire `replyright_kernel`** into `outlook_dashboard/ai.py` when ready to replace/supplement the on-demand OpenAI call.
7. **Add `OPENAI_API_KEY`** only when ready to test the AI response button.
