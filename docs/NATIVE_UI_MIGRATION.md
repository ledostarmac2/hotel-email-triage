# Native UI Migration Investigation

Last updated: 2026-05-18

## Current Problem

ReplyRight v0.1.0 exposed the pywebview/FastAPI implementation detail to users when the downloaded app displayed a localhost refused-to-connect page. That is a release blocker.

v0.1.1 keeps pywebview temporarily but gates window creation on backend health and removes external browser fallback. The longer-term direction should be a native desktop UI that does not depend on browser chrome, WebView navigation, or localhost as the visible app surface.

The initial non-production PySide6 scaffold now lives in `replyright_core/`, `replyright_qt/`, and `docs/PYSIDE6_MIGRATION_PLAN.md`.

## Current UI Architecture

Active UI path:

```text
run_desktop.py
  -> FastAPI app in outlook_dashboard/main.py
  -> static HTML/CSS/JS in outlook_dashboard/static/
  -> pywebview / WebView2 desktop window
```

Static UI files:

- `outlook_dashboard/static/index.html`
- `outlook_dashboard/static/login.html`
- `outlook_dashboard/static/reset_password.html`
- `outlook_dashboard/static/styles.css`
- `outlook_dashboard/static/app.js`

Inactive:

- `app/` is an inactive Next.js scaffold.
- `replyright_kernel/` is experimental and not wired into production.

## Screens Found

Primary dashboard:

- Login screen at `/login`
- Forgot-password overlay inside `login.html`
- Reset password screen at `/reset-password`
- Main dashboard shell at `/`
- Sidebar views: Inbox, Urgent, VIP, Missing Info, Admin
- Update banner with release notes and install button
- Topbar with Refresh Inbox
- Metrics strip
- Search and filters
- Priority queue
- Email detail pane
- Conversation thread view
- Status selector
- Feedback form with urgency, owner, category, contact type, sentiment, status, summary rating, and reply rating
- AI recommended response modal
- Admin-only signal inspector toggle in email detail

Admin dashboard screens rendered by `app.js`:

- Overview metrics
- Analysis engine breakdown
- AI provider configuration
- Correction statistics
- Low-confidence email table
- Owner and urgency misclassification drilldowns
- Suggested rule candidates with Reject and Dismiss controls
- User management and invite/reset/delete controls
- Training pipeline run/status card
- Local classifier train button
- Version/update card
- Dual-labeled training stats
- Human review queue
- Model health card
- Feature importance table
- Sender profile lookup
- Audit log table

Diagnostics and update screens:

- `/api/health`
- `/healthz`
- `/api/version`
- `/api/update-available`
- `/api/update/download`

## Backend Endpoints Used By The UI

Auth:

- `GET /login`
- `POST /login`
- `GET /reset-password`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/invite`
- `GET /api/auth/users`
- `DELETE /api/auth/users/{user_id}`
- `POST /api/auth/users/{user_id}/reset-password`

Dashboard and config:

- `GET /`
- `GET /api/config`
- `GET /api/taxonomy`
- `GET /api/health`
- `GET /healthz`
- `GET /api/version`
- `GET /api/update-available`
- `POST /api/update/download`

Inbox and analysis:

- `POST /api/outlook-desktop/export-inbox`
- `POST /api/outlook-desktop/import-json`
- `POST /api/sync/outlook`
- `POST /api/ai/process-pending`
- `GET /api/emails`
- `GET /api/emails/{email_id}`
- `POST /api/emails/{email_id}/analyze`
- `POST /api/emails/{email_id}/feedback`
- `PATCH /api/emails/{email_id}/status`

Admin and intelligence:

- `GET /api/admin/stats`
- `GET /api/admin/training/status`
- `POST /api/admin/training/run`
- `GET /api/admin/training/examples`
- `PATCH /api/admin/training/examples/{example_id}/review`
- `GET /api/admin/training/dual-labeled-stats`
- `POST /api/admin/classifier/train`
- `GET /api/admin/intelligence/health`
- `GET /api/admin/models/feature-importance`
- `GET /api/admin/intelligence/sender-profile`
- `GET /api/admin/intelligence/signals`
- `GET /api/admin/prompts`
- `PATCH /api/admin/prompts/{prompt_id}`
- `GET /api/rule-candidates`
- `POST /api/rule-candidates/status`

Graph OAuth endpoints exist but are not the primary live path:

- `GET /auth/login`
- `GET /auth/callback`

## Frontend State Currently In JavaScript

`outlook_dashboard/static/app.js` manages:

- Auth boot and redirect state
- Current user and admin visibility
- Current sidebar view
- Current filters
- Current selected email/conversation
- Email list cache
- Taxonomy/config cache
- Update banner dismissal in localStorage
- Refresh progress copy
- Admin dashboard rendering state
- Training pipeline results
- Modal state for AI response draft
- Toast notifications
- Client-side view filters for Urgent, VIP, and Missing Info

## Backend Module Classification

Reusable unchanged:

- `taxonomy.py`
- `taxonomy_meta.py`
- `signal_extractor.py`
- `hotel_entities.py`
- `travel_programs.py`
- `urgency_engine.py`
- `redaction.py`
- `runtime_log.py`
- `platform_compat.py`

Reusable with minor refactor:

- `ai.py` - keep classification logic, but expose cleaner service functions for native UI actions.
- `database.py` - keep SQLite schema and persistence, but separate admin view models from UI routes over time.
- `graph.py` - keep Graph OAuth/read-only sync helpers.
- `outlook_desktop.py` - keep read-only COM importer and macro fallback.
- `auth.py` - keep Supabase Auth helpers, but add native session facade for non-cookie UI state.
- `config.py` - keep environment/runtime path handling.
- `local_classifier.py` - keep training/prediction, add progress callbacks later.
- `sender_intelligence.py` - keep profile cache and bias layer.
- `training_pipeline.py` - keep core pipeline, add progress/event hooks for native UI.
- `supabase_client.py` - keep shared rules/prompts/senders helpers.
- `updater.py` - keep release check, but native UI should launch installer through an explicit service.

UI-coupled and needs extraction:

- `outlook_dashboard/main.py` - route handlers mix auth, view rendering, admin orchestration, and service calls.
- `outlook_dashboard/static/app.js` - all current frontend state and rendering.
- `outlook_dashboard/static/index.html`, `login.html`, `reset_password.html`, and `styles.css`.
- `run_desktop.py` - launcher and pywebview bridge only; should disappear after native UI migration.

Should be deprecated:

- Browser fallback behavior in `run_desktop.py` is deprecated and removed for v0.1.1.
- Raw-EXE release publishing should be deprecated as a user-facing release path.
- `app/` remains inactive and should not be revived without a separate migration decision.

## Option A: Keep pywebview Temporarily

What must be fixed:

- Health-gate window creation.
- Use `/healthz` for startup readiness.
- Remove external browser fallback.
- Show controlled startup errors.
- Publish installer-first releases.
- Bundle and install WebView2 reliably.

What it buys:

- A fast v0.1.1 repair.
- Minimal code churn.
- Existing UI continues working.
- Training/admin/classifier work is not disrupted.

Why it is not the long-term zero-browser solution:

- It still depends on WebView2.
- The UI is still HTML/JS behind a local FastAPI server.
- WebView startup failures can still happen.
- Localhost remains part of the internal runtime.
- Native Windows app polish is limited by webview behavior.

## Option B: PySide6 / Qt Native UI

Recommendation: best v0.2.0 target if the goal is to remove browser/WebView UI dependency while keeping Python intelligence modules.

Do not use `QWebEngineView` as the main UI.

Proposed structure:

```text
replyright_core/
  services/
  models/
  repositories/
  auth/
  training/

replyright_qt/
  app.py
  windows/
  widgets/
  viewmodels/
  workers/
  resources/

outlook_dashboard/
  legacy FastAPI bridge during transition
```

Existing modules to preserve:

- SQLite/database layer
- Outlook COM importer
- Graph helpers
- Supabase Auth helpers
- Supabase shared learning helpers
- Redaction
- Local classifier
- Hotel entities, travel programs, urgency engine
- Taxonomy and taxonomy metadata
- Runtime logging

FastAPI endpoints that become direct Python service calls:

- Refresh Inbox -> `InboxService.refresh_outlook()`
- List emails -> `InboxService.list_conversations()`
- Get detail -> `InboxService.get_conversation()`
- Analyze -> `AnalysisService.analyze_conversation()`
- Feedback -> `FeedbackService.save_feedback()`
- Training run -> `TrainingService.run_batch()`
- Classifier train -> `ClassifierService.train()`
- Admin stats -> `AdminService.dashboard()`
- Update download -> `UpdateService.download_and_launch_installer()`

Native Qt screens needed:

- Login window
- Password reset flow
- Main inbox shell
- Sidebar queue filters
- Metrics strip
- Email list/table
- Email detail/thread pane
- Feedback editor
- AI suggestion modal
- Admin overview
- User management
- Rule candidates
- Training pipeline
- Human review queue
- Model health and feature importance
- Sender profile lookup
- Audit logs
- Version/update diagnostics

Background tasks:

- Use `QThreadPool`/`QRunnable` or `QThread` workers for Outlook import, AI analysis, training pipeline, classifier training, and update checks.
- Keep UI responsive with progress signals and cancellation where practical.

Login/session state:

- Store Supabase session tokens in memory for the running app.
- Persist only where needed with the same privacy expectations as current cookies.
- Keep admin checks explicit in service calls.

Email list/detail:

- Use `QTableView` or `QListView` with a model for conversation rows.
- Use a detail panel with structured fields and read-only message text.
- Avoid rendering raw HTML email bodies unless sanitized.

Charts/tables:

- Start with Qt tables and simple progress bars.
- Add chart widgets only after admin metrics stabilize.

Classifier/training progress:

- Expose progress callbacks from training services.
- Show batch counts and final metrics.
- Keep model promotion deliberate.

Diagnostics/updater:

- Native diagnostics window should show build version, commit, DB path, SQLite status, Supabase status, Outlook COM status, WebView status no longer relevant, AI provider status, classifier version, last sync, and last training.
- Updater should download and launch the installer.

Packaging:

- PyInstaller can package PySide6, but the spec must collect Qt plugins/platforms.
- Inno Setup remains the installer.

Risks and unknowns:

- More UI code to write.
- Qt packaging can be larger than pywebview.
- Need careful threading around Outlook COM.
- Need to preserve all current admin workflows.
- Need native styling work to avoid a rushed utility look.

Estimated effort:

- v0.2.0 native MVP with login, inbox, detail, refresh, feedback, and AI modal: 2 to 4 focused weeks.
- Admin parity with training/classifier/rules/users/audit/update: 2 to 3 additional weeks.
- Full polish, installer QA, and beta hardening: 1 to 2 additional weeks.

## Option C: C#/.NET WPF Or WinUI

Proposed structure:

```text
ReplyRight.Desktop/
  WPF or WinUI app
  Views/
  ViewModels/
  Services/

replyright_python/
  packaged Python service or CLI

outlook_dashboard/
  legacy Python app during transition
```

Python strategy options:

- Keep Python as a local backend process and call it over HTTP.
- Keep Python as subprocess/CLI commands for discrete tasks.
- Use Python.NET for in-process calls.
- Use SQLite/file boundary between C# UI and Python workers.
- Port Python logic to C# over time only if justified.

Recommended WPF bridge if chosen:

- Short term: C# UI plus local Python backend process.
- Medium term: define service contracts and slowly port only stable logic.

Hardest modules to port:

- `ai.py`
- `local_classifier.py`
- `hotel_entities.py` date parsing behavior
- `outlook_desktop.py` COM importer details
- `training_pipeline.py`
- Supabase/auth edge cases

Outlook COM implications:

- C# can use COM well, but current Python importer is already working and tested.
- A full C# port would need fresh Outlook safety testing.

Graph/Supabase/SQLite/classifier implications:

- Graph and Supabase are portable but need new client implementations.
- SQLite is easy to share.
- scikit-learn classifier strongly favors keeping Python.

Installer implications:

- WPF/WinUI has a very strong Windows install story.
- Inno Setup can still package the app, or MSIX can be evaluated later.

Risks and unknowns:

- Much larger rewrite.
- Two-language system can be harder to debug.
- Python packaging still exists if classifier and AI logic stay Python.
- Higher chance of feature regression across admin/training flows.

Estimated effort:

- WPF shell around existing Python backend: 4 to 8 weeks.
- Full native parity with admin/training/update flows: 8 to 12+ weeks.
- Porting most Python logic to C#: not recommended now.

## Decision Matrix

| Option | Speed | Zero-browser UX | Reuse Python core | Packaging risk | Long-term fit |
| --- | --- | --- | --- | --- | --- |
| A: patched pywebview | Highest | Partial | High | Medium | Short-term only |
| B: PySide6 native | Medium | High | Highest | Medium | Best fit |
| C: WPF/WinUI | Lowest | High | Medium | Medium-high | Possible later |

## Recommended Path

1. v0.1.1: ship the emergency pywebview startup repair plus installer-first release.
2. v0.1.x: keep stabilizing training/classifier/admin workflows without UI rewrite.
3. v0.2.0: migrate the main user workflow to PySide6 native UI.
4. v0.2.x: migrate admin screens to PySide6 after the inbox workflow is stable.
5. Keep FastAPI available only as a legacy bridge or test harness during migration.

## Acceptance Criteria For Native UI

- No WebView2 dependency for the main UI.
- No visible localhost URL or browser error can appear.
- Login, inbox, detail, refresh, feedback, and AI suggestion work natively.
- Admin training/classifier/rules/users/update workflows have native equivalents before retiring the web UI.
- Outlook remains read-only.
- AI drafts remain human-reviewed.
- Tests cover service logic independent of UI toolkit.
- Installer remains the primary release artifact.
