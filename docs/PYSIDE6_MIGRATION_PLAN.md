# PySide6 Migration Plan

Last updated: 2026-05-18

## Decision

PySide6 is the recommended native UI target for ReplyRight v0.2.0.

The current v0.1.1 bridge may keep pywebview temporarily, but pywebview is not the long-term product shell. The native app must not use `QWebEngineView`, Electron, Tauri, or another browser/WebView engine as the primary UI.

## Scaffold

New non-production scaffold:

```text
replyright_core/
  services/
  models/
  adapters/
  app_state.py

replyright_qt/
  main_qt.py
  windows/
  widgets/
  viewmodels/
  resources/
```

The active product remains:

```text
outlook_dashboard/
run_desktop.py
```

## Service Boundaries To Extract

1. Auth service
   - Login/logout/current user
   - First-run admin setup
   - User list/invite/delete/reset wrappers

2. Inbox service
   - Conversation list
   - Conversation detail/thread loading
   - Local status updates
   - Read-only Outlook refresh

3. Analysis service
   - Deterministic triage
   - Hotel entities, travel programs, urgency engine
   - Local classifier prediction
   - Shared rules and sender intelligence
   - Optional AI analysis/draft request

4. Feedback service
   - Correction capture
   - Rule candidate detection
   - Supabase feedback upload/queue

5. Training service
   - Training pipeline run/status
   - Human review queue
   - Local classifier train/status/feature importance

6. Diagnostics service
   - `/healthz` equivalent
   - Version/build info
   - Platform checks
   - Updater status

## Screen Migration Map

| Current Screen | Future Qt Equivalent | Notes |
| --- | --- | --- |
| Login | Login window | Supabase Auth-backed, no browser |
| First-run setup | Setup window | Create first admin when none exists |
| Inbox/Urgent/VIP/Missing Info queues | Main window with queue tabs | Use Qt item models for dense scanning |
| Email detail/thread | Conversation detail pane | Preserve quoted-thread cleanup and risk display |
| Feedback form | Feedback panel/dialog | Keep structured corrections and ratings |
| AI suggestion modal | Reply suggestion dialog | Human review only; no sending |
| Admin overview | Admin window/tab | Protected by admin role |
| Rules/users/prompts | Admin widgets | Keep audit records |
| Training/model health | Training widgets | Background worker with progress/status |
| Signal inspector/sender profile/audit | Diagnostics/admin widgets | Read-only diagnostic views |
| Update/version | Diagnostics/update panel | Installer-first update flow |

## Background Tasks

Use Qt worker threads or a small task runner for:

- Outlook refresh/import
- AI calls
- Supabase sync
- Training export
- Local classifier training
- Update checks

UI code must not block the event loop.

## Packaging

The PySide6 shell should eventually have a separate PyInstaller entry point:

```text
replyright_qt/main_qt.py
```

Keep the Inno Setup installer-first release model:

```text
ReplyRightSetup-v{version}.exe
```

Do not add PySide6 to production requirements until a runnable native slice exists and packaging has been verified.

## Acceptance Criteria For First Native Slice

- Starts without FastAPI or pywebview.
- Does not import `QWebEngineView`.
- Shows login/setup.
- Lists conversations from local SQLite through a core service.
- Opens conversation detail.
- Saves structured feedback.
- Shows health/version diagnostics.
- Preserves read-only Outlook posture.
- Passes existing tests plus new Qt service/viewmodel tests.

## Non-Goals For The Scaffold

- No full UI rewrite in this step.
- No reply sending.
- No migration to `app/`.
- No `replyright_kernel/` production wiring.
- No PySide6 dependency added to production requirements yet.
