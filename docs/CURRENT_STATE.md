# Current State

Last updated: 2026-05-17 (v0.1.0 — Phase 7 complete: enterprise deployment, Supabase Auth, bundled credentials, 175 tests)

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked conversation queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and now uses read-only `pywin32` COM import as the primary path. The legacy `ExportNYCWAReservationsInboxOnly` VBA macro remains a fallback when direct import dependencies are unavailable.
- Refresh Inbox now attempts OpenAI classification when `OPENAI_API_KEY` is configured. The dashboard `OPENAI_MODEL` default is `gpt-5.4-nano`, selected after checking official OpenAI docs on 2026-05-17 for low-cost classification/extraction suitability. If OpenAI is not configured and `GOOGLE_AI_API_KEY` is present, Refresh Inbox attempts Google AI Studio/Gemini classification with structured JSON output. Local deterministic triage remains the fallback when external AI is unavailable or errors.
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
  - `triage_feedback` stores per-conversation correction notes plus optional corrected urgency, owner, category, contact type, sentiment, status, summary quality rating, and reply quality rating.
  - `POST /api/emails/{email_id}/feedback` applies feedback immediately to the selected conversation.
  - Similar future messages can reuse stored local feedback patterns.
- A CCA/completed-form pattern now routes to Reservations with concise steps to apply the form and confirm completion.
- Urgency is deliberately more conservative: level 5 is reserved for same/next-day operational blockers or serious risk, while completed/thank-you/form-submission updates are lowered unless a high-risk signal is present.
- `python -m pytest tests/ -x --timeout=30` passes with **175 tests** (35 subtests). Python compile checks for active source files and a FastAPI health smoke also pass.
- `dist\ReplyRight.exe` was rebuilt after adaptive triage changes. Packaged health check succeeded, and current packaged data rendered 28 conversation groups with urgency distribution `2:14, 3:4, 4:7, 5:3`.
- `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` captures the broader Supabase/shared-learning roadmap.
- Confidence scoring (10–95%) is computed per email and shown as a color-coded pill in the UI.
- Rule candidate engine mines local feedback for recurring correction patterns. Three matching corrections create visible candidates; five or more mark the rule as auto-promoted for hands-off shared learning.
- Admin Suggested Rules now includes emergency `Reject` and `Dismiss` controls. Dismissed candidates are hidden locally; rejected candidates stay visible as rejected and are skipped by Supabase auto-promotion.
- Login is gated by local ReplyRight accounts. The configured admin account is read from `REPLYRIGHT_ADMIN_EMAIL` / `REPLYRIGHT_ADMIN_PASSWORD` in `.env`; startup creates or repairs that admin hash if it already exists.
- Login failures render a persistent static error message with an X close button and preserve the typed email address. Dashboard action failures such as invite/reset errors now use a persistent dismissable error toast.
- Auth middleware protects `/api/auth/me` and admin endpoints again. Public auth routes are limited to login/logout/forgot-password/reset-password, fixing the post-login dashboard boot loop.
- Admin view now has its own dashboard shell: the Refresh Inbox button is hidden while Admin is active, the topbar changes to Admin, and leaving Admin restores/rebinds the inbox queue/detail DOM so Inbox, Urgent, VIP, and Missing Info render correctly again.
- `dist\ReplyRight.exe` was rebuilt after the admin navigation fix and shortcuts were refreshed. A headless Edge/Selenium check verified Admin -> Inbox -> Urgent navigation, including Refresh Inbox visibility.
- Roadmap audit completed and recorded in `docs/HANDOFF.md`. Phase 1 is mostly complete; the next blanks are structured feedback controls, Supabase durable sync/cache, hands-off rule auto-promotion, and a true staged AI pipeline.
- Brian answered the roadmap questions: summary quality and reply quality should be 1-5 ratings; shared learning rules should auto-promote hands-off with no required admin monitoring; multi-property/cross-property support is irrelevant and should be removed from the roadmap because ReplyRight is only for this hotel.
- Supabase approved rules are cached durably in local SQLite, and failed feedback uploads are queued locally for retry on the next configured startup.
- Supabase startup sync now also downloads and durably caches active prompt versions and known sender mappings. Known sender mappings are applied during local triage by sender domain for owner/contact-type corrections.
- A dedicated import smoke test now imports the active dashboard and Semantic Kernel modules so missing optional dependencies or broken import-time assumptions are caught earlier.
- Phase 7 of `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` now defines the long-term local hotel-specific training direction: import historical completed emails, redact/sanitize PII, AI-label sanitized examples, human-review samples, store a Supabase training dataset, train lightweight local classifiers, route by confidence, and use external AI only for low-confidence, complex, sensitive, summary, or reply-drafting work.
- Phase 7 should start with local classification targets only: urgency, owner, category, status, missing information, reply required, and escalation required. Do not try to train local polished reply writing first.
- **v0.1.0 optimization pass (2026-05-17):** All code optimizations applied — dead category-check branch removed from `ai.py`, bare JSON parse in `_analyze_with_claude` wrapped with proper error handling, SMTP code deduplicated in `auth.py`, three near-identical Supabase download functions unified in `supabase_client.py`, httpx.Client reused across `promote_rule_candidates` loop, `secrets` moved to top-level import in `main.py`, rate-limit bucket TTL pruning added, `registry.py` plugin loop introduced.
- **Phase 7 enterprise deployment (2026-05-17):**
  - **Supabase Auth migration**: All user authentication, session management, and admin provisioning now go through Supabase `/auth/v1/*` endpoints. No local SQLite user tables. Sessions stored as `access_token|||refresh_token` cookie (`rr_session`). Token refresh handled transparently in `_AuthMiddleware`.
  - **Bundled credentials**: `outlook_dashboard/bundled_secrets.py` ships XOR-obfuscated Supabase URLs, keys, Anthropic API key, and model name — committed to GitHub so any machine with the repo can connect to the DB and run AI with zero manual configuration. `.env` takes precedence when present.
  - **Claude AI usage rule (CRITICAL)**: Claude/Anthropic is called ONLY when the user clicks the single-email "Analyze" button (`analyze_email()`). Bulk Refresh uses OpenAI → Google → heuristic only (no Claude). Violating this burns credits on every inbox refresh.
  - **EXE now includes anthropic**: `build_exe.ps1` uses `--collect-all anthropic` so the packaged EXE can call Claude without "No module named 'anthropic'" errors.
  - **Docker**: `Dockerfile` + `docker-compose.yml` for web-only server mode on Linux/Mac.
  - **Inno Setup installer**: `installer/replyright_setup.iss` builds a Windows installer wizard.
  - **Auto-updater**: `outlook_dashboard/updater.py` checks `ledostarmac2/hotel-email-triage` GitHub releases on startup.
  - **Platform compat**: `outlook_dashboard/platform_compat.py` provides `IS_WINDOWS`, `HAS_OUTLOOK_COM`, `HAS_WEBVIEW` flags for cross-platform safe guards.
  - **One-command setup**: `setup.ps1` installs Python, clones repo, creates venv, installs deps, builds EXE, and creates shortcuts. Run with: `irm https://raw.githubusercontent.com/ledostarmac2/hotel-email-triage/main/setup.ps1 | iex`
  - **GitHub Actions CI**: lint (syntax + pytest) on windows-latest + EXE build artifact + Docker health check on ubuntu-latest + release job triggered on `v*.*.*` tags that creates a GitHub Release with EXE attached.

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

Copy `.env.example` to `.env` for local runs. `.env` must not be committed. All credentials are bundled encrypted in `bundled_secrets.py` so the app works out-of-the-box even without a `.env` file — but `.env` always takes precedence.

Important variables:

- `ANTHROPIC_API_KEY` — bundled; override in `.env` if rotating. Used ONLY for single-email Analyze button (Claude Opus).
- `ANTHROPIC_MODEL` — default `claude-opus-4-7` (bundled).
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — bundled; all auth and data goes through Supabase.
- `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` — Supabase Auth admin account credentials. `ensure_admin()` creates/repairs this user in Supabase on startup.
- `OPENAI_API_KEY` / `OPENAI_MODEL` — for Refresh Inbox bulk classification (not Analyze button).
- `GOOGLE_AI_API_KEY` / `GOOGLE_AI_MODEL` — fallback for Refresh Inbox when OpenAI not configured.
- `APP_HOST=127.0.0.1`, `APP_PORT=8000`
- `OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations`, `OUTLOOK_EXPORT_FOLDER=Inbox`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (for password reset emails).

**GitHub Actions Secrets** (set in repo Settings → Secrets → Actions):
- `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — used by CI to build the EXE and run the Docker health check.

**Supabase setup** (one-time): paste `docs/supabase_schema.sql` into the Supabase SQL Editor and run it. Creates `feedback_events`, `classification_rules`, `known_senders`, and `prompt_versions` tables with RLS policies.

## Current Risks

- The legacy VBA macro fallback must be installed manually only on machines where the direct `pywin32` import path is unavailable.
- The app must be running before Refresh Inbox; direct import happens in-process through the FastAPI endpoint.
- Outlook direct COM import depends on classic Outlook for Windows and bundled `pywin32`; if unavailable, ReplyRight falls back to the legacy `/autorun` VBA macro path.
- AI drafts are suggestions only and require human review.
- Supabase integration is wired: `upload_feedback_event()` fires after every correction and `download_approved_rules()` runs on startup. Uploads are a no-op until `SUPABASE_URL`/`SUPABASE_KEY` are set in `.env` and the schema is created (paste `docs/supabase_schema.sql` into the Supabase SQL Editor). **Both Supabase keys shared in session chat must be rotated before use.**
- The Google AI Studio key shared in session chat must also be rotated before use. Do not store pasted/shared keys in tracked files or docs.
- `.env` and `dist\.env` currently contain local admin/SMTP credentials and must not be committed or shared.
- This app intentionally does not mutate Outlook messages; adding send/archive/move/category actions requires a new design and approval.
- Local mailbox exports and SQLite data are ignored for privacy and are not portable through git.
- Phase 7 training must remain privacy-preserving by default. Do not store raw hotel email bodies, guest PII, reservation numbers, payment details, or attachments in Supabase training tables unless Brian explicitly approves a new override.

## Semantic Kernel Orchestration Layer

A new `replyright_kernel/` Python package implements the foundational SK orchestration layer:

- **PriorityTriagePlugin** — local urgency scoring 1–5 (regex/keyword, no LLM cost)
- **ExecutiveSummaryPlugin** — strips HTML, quoted threads, signatures, legal footers, tracking noise; enforces 8 000-char token budget
- **AuditCompliancePlugin** — pre-display compliance scan; blocks guarantees, fault admissions, payment leakage, legal/medical/discrimination risk language, unapproved promises
- **engine.py / registry.py** — builds and registers the kernel; clearly labelled extension points for future Graph and CRM plugins
- **demo.py** — runnable four-step pipeline demo (`python -m replyright_kernel.demo`)

The layer is additive. It does not touch the existing FastAPI dashboard, Next.js scaffold, or Outlook read path.

Tests: `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` (59 tests, no API key required).

`OPENAI_MODEL` defaults to `gpt-5.5` in the kernel layer; the dashboard uses `gpt-5.4-nano` unless overridden. `KERNEL_LOG_LEVEL` controls kernel log verbosity.

## Recommended Next Steps

1. **Supabase schema**: if not yet run, paste `docs/supabase_schema.sql` into the Supabase SQL Editor (project `dxalumiijcfmwzmosijf`) and execute it once to create all tables.
2. **GitHub Secrets**: in the GitHub repo Settings → Secrets → Actions, confirm `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` are set so CI can build and test.
3. **First GitHub Release**: push a tag (`git tag v0.1.0 && git push origin v0.1.0`) to trigger the release job — it builds the EXE and posts a GitHub Release with the installer attached.
4. **Local classifier training (Phase 7 long-term)**: import historical completed emails → redact PII → AI-label → human-review samples → store sanitized Supabase training set → train lightweight local classifiers. Start with urgency, owner, category, status, missing_information targets only.
5. **Refresh check**: click Refresh Inbox once and visually confirm the feedback box, resized window behavior, and Outlook-like independent scrolling.
6. **Login check**: use the local ReplyRight admin credentials from `dist\.env`; bad credentials should show a persistent error with an X, good credentials should enter the app.
7. **Spot-check triage**: review conversations formerly over-scored as urgency 4/5, especially completed CCA/payment form threads and friendly travel-agent replies.
8. **If launch fails**: inspect `dist\data\replyright-startup.log`. Look for `pythonnet (clr) is not available`; if seen, delete `.vendor` and re-run `.\build_exe.ps1` so pip re-installs pythonnet.
9. **Use the roadmap**: read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` before broad architecture work, especially Supabase shared learning and staged AI pipeline. Ignore multi-property/cross-property ideas unless Brian reopens them.
10. **Wire `replyright_kernel`** into `outlook_dashboard/ai.py` only where it supports the new split: OpenAI refresh classification, local fallback/tests, and Claude Opus `AI Suggestion`.
11. **Admin rules check**: after entering real feedback, confirm Suggested Rules shows Reject/Dismiss and that Dismiss removes a candidate from the local admin view.
12. **Phase 7 local learning**: when ready, implement incrementally in the documented order: Supabase training tables, sanitized training records, PII redaction, historical importer, AI batch labeler, human review queue, local classifier training, runtime prediction, admin controls, model activation/rollback, and metrics.
