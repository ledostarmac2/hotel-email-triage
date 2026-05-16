# Current State

Last updated: 2026-05-16 (roadmap direction decisions)

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked conversation queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and now uses read-only `pywin32` COM import as the primary path. The legacy `ExportNYCWAReservationsInboxOnly` VBA macro remains a fallback when direct import dependencies are unavailable.
- Current bulk imports use local rules for speed, but the target direction changed: Refresh Inbox should use OpenAI to assign all triage metadata for imported emails. Claude Opus should be reserved for explicit `AI Suggestion` drafting/refinement.
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
- `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` captures the broader Supabase/shared-learning roadmap.
- Confidence scoring (10–95%) is computed per email and shown as a color-coded pill in the UI.
- Rule candidate engine mines local feedback for recurring correction patterns and surfaces them as a dismissable banner.
- Login is gated by local ReplyRight accounts. The configured admin account is read from `REPLYRIGHT_ADMIN_EMAIL` / `REPLYRIGHT_ADMIN_PASSWORD` in `.env`; startup creates or repairs that admin hash if it already exists.
- Login failures render a persistent static error message with an X close button and preserve the typed email address. Dashboard action failures such as invite/reset errors now use a persistent dismissable error toast.
- Auth middleware protects `/api/auth/me` and admin endpoints again. Public auth routes are limited to login/logout/forgot-password/reset-password, fixing the post-login dashboard boot loop.
- Admin view now has its own dashboard shell: the Refresh Inbox button is hidden while Admin is active, the topbar changes to Admin, and leaving Admin restores/rebinds the inbox queue/detail DOM so Inbox, Urgent, VIP, and Missing Info render correctly again.
- `dist\ReplyRight.exe` was rebuilt after the admin navigation fix and shortcuts were refreshed. A headless Edge/Selenium check verified Admin -> Inbox -> Urgent navigation, including Refresh Inbox visibility.
- Roadmap audit completed and recorded in `docs/HANDOFF.md`. Phase 1 is mostly complete; the next blanks are structured feedback controls, Supabase durable sync/cache, hands-off rule auto-promotion, and a true staged AI pipeline.
- Brian answered the roadmap questions: summary quality and reply quality should be 1-5 ratings; shared learning rules should auto-promote hands-off with no required admin monitoring; multi-property/cross-property support is irrelevant and should be removed from the roadmap because ReplyRight is only for this hotel.
- For the OpenAI refresh-classification work, future agents must verify current official OpenAI model/pricing docs and choose the best available free-tier or lowest-cost suitable OpenAI model. Do not hard-code a stale model assumption in docs or code.

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
- `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` for the local ReplyRight admin account.
- SMTP invite/reset variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- `OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations`
- `OUTLOOK_EXPORT_FOLDER=Inbox`
- Optional Microsoft Graph values: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`, `MICROSOFT_REDIRECT_URI`, `SHARED_MAILBOX_EMAIL`.

## Current Risks

- The legacy VBA macro fallback must be installed manually only on machines where the direct `pywin32` import path is unavailable.
- The app must be running before Refresh Inbox; direct import happens in-process through the FastAPI endpoint.
- Outlook direct COM import depends on classic Outlook for Windows and bundled `pywin32`; if unavailable, ReplyRight falls back to the legacy `/autorun` VBA macro path.
- AI drafts are suggestions only and require human review.
- Supabase integration is wired: `upload_feedback_event()` fires after every correction and `download_approved_rules()` runs on startup. Uploads are a no-op until `SUPABASE_URL`/`SUPABASE_KEY` are set in `.env` and the schema is created (paste `docs/supabase_schema.sql` into the Supabase SQL Editor). **Both Supabase keys shared in session chat must be rotated before use.**
- `.env` and `dist\.env` currently contain local admin/SMTP credentials and must not be committed or shared.
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

1. **Packaged UI check**: launch the rebuilt Desktop shortcut and confirm Admin -> Inbox/Urgent/VIP/Missing Info leaves Admin correctly and restores the Refresh Inbox button only outside Admin.
2. **Roadmap blanks**: start with direct feedback controls for category/contact/sentiment, then 1-5 summary/reply quality ratings.
3. **Supabase sync**: add durable local cache/queue for approved rules, prompt versions, known senders, and failed feedback uploads.
4. **AI pipeline**: make Refresh Inbox use staged OpenAI classification for imported messages, with local triage as fallback and Claude Opus reserved for `AI Suggestion`.
5. **Refresh check**: click Refresh Inbox once and visually confirm the feedback box, resized window behavior, and Outlook-like independent scrolling.
6. **Login check**: use the local ReplyRight admin credentials from `dist\.env`; bad credentials should show a persistent error with an X, good credentials should enter the app.
7. **Spot-check triage**: review conversations formerly over-scored as urgency 4/5, especially completed CCA/payment form threads and friendly travel-agent replies.
8. **If launch fails**: inspect `dist\data\replyright-startup.log`. Look for `pythonnet (clr) is not available`; if seen, delete `.vendor` and re-run `.\build_exe.ps1` so pip re-installs pythonnet.
9. **Use the roadmap**: read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` before broad architecture work, especially Supabase shared learning and staged AI pipeline. Ignore multi-property/cross-property ideas unless Brian reopens them.
10. **Wire `replyright_kernel`** into `outlook_dashboard/ai.py` only where it supports the new split: OpenAI refresh classification, local fallback/tests, and Claude Opus `AI Suggestion`.
