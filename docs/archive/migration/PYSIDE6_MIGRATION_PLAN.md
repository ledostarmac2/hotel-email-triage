# PySide6 Migration Plan

Last updated: 2026-05-19

---

## Decision

PySide6 is the target native UI framework for ReplyRight v0.2.0.

The current v0.1.1 bridge keeps pywebview temporarily for emergency repair continuity,
but pywebview is not the long-term product shell.

**Non-negotiable rules:**
- Do not use `QWebEngineView` as the primary UI surface — ever.
- Do not use pywebview in the new native app shell.
- Do not use Electron.
- Do not use Tauri.
- Do not use any browser/WebView engine as the primary application UI.
- Native Qt widgets only.

Rationale: The v0.1.0 incident (user-visible localhost refused-to-connect page) was
caused by the pywebview/WebView2 layer. The only durable fix is eliminating the browser
dependency from the desktop shell entirely.

---

## Scaffold (current state)

```text
replyright_core/                     — Framework-neutral service layer
  models/
    email_models.py                  — Conversation, EmailMessage, TriageResult dataclasses
    user_models.py                   — User, Session dataclasses
  services/
    auth_service.py                  — AuthServiceProtocol
    inbox_service.py                 — InboxServiceProtocol
  adapters/
    sqlite_adapter.py                — SqliteAdapterProtocol
  app_state.py                       — AppState dataclass

replyright_qt/                       — PySide6 native shell scaffold
  main_qt.py                         — Native helper; direct execution raises until native slice ready
  adapters/                          — Supabase auth and SQLite inbox adapter scaffolds
  workers.py                         — QThread worker scaffolds for native auth/inbox loading
  windows/
    login_window.py                  — LoginWindow skeleton
    main_window.py                   — MainWindow skeleton
  widgets/
    conversation_list.py             — ConversationListWidget skeleton
  viewmodels/
    inbox_viewmodel.py               — InboxViewModel (framework-neutral)
  resources/
```

The active production path remains:
```text
run_desktop.py -> outlook_dashboard/main.py (FastAPI) -> static HTML/CSS/JS -> pywebview
```

`run_desktop.py --native` / `REPLYRIGHT_NATIVE=1` is development-only scaffold access and is not the v0.1.1 production launcher.

---

## Modules to preserve (do not rewrite without test backing)

These modules are called by the future service layer, not replaced:

| Module | Purpose |
|---|---|
| `outlook_dashboard/ai.py` | AI analysis/draft request (Anthropic, OpenAI, Gemini) |
| `outlook_dashboard/signal_extractor.py` | Signal extraction from email text |
| `outlook_dashboard/sender_intelligence.py` | Sender reputation and pattern scoring |
| `outlook_dashboard/local_classifier.py` | Scikit-learn local triage classifier |
| `outlook_dashboard/hotel_entities.py` | Hotel-specific entity recognition |
| `outlook_dashboard/travel_programs.py` | Travel program and loyalty entity matching |
| `outlook_dashboard/urgency_engine.py` | Urgency scoring |
| `outlook_dashboard/taxonomy_meta.py` | Category/label taxonomy |
| `outlook_dashboard/redaction.py` | PII redaction (must not be weakened) |
| `outlook_dashboard/supabase_client.py` | Supabase cloud sync |
| `outlook_dashboard/database.py` | Local SQLite read/write |
| `outlook_dashboard/training_pipeline.py` | Local classifier training |
| `outlook_dashboard/auth.py` | Supabase Auth integration |

---

## Modules to extract into service interfaces

These are called through `replyright_core/services/` Protocols in the native app:

| Service | Backed by |
|---|---|
| `AuthServiceProtocol` | `outlook_dashboard/auth.py` |
| `InboxServiceProtocol` | `outlook_dashboard/database.py` + `outlook_dashboard/main.py` inbox logic |
| `AnalysisServiceProtocol` (future) | `outlook_dashboard/ai.py` + deterministic pipeline |
| `FeedbackServiceProtocol` (future) | `outlook_dashboard/supabase_client.py` |

---

## Screen migration map

| Current screen | Future Qt equivalent | Status |
|---|---|---|
| Login | `LoginWindow` | Scaffold only |
| First-run admin setup | `SetupWindow` (future) | Not yet |
| Inbox / queue tabs | `MainWindow` with tab widget | Scaffold only |
| Conversation detail | `ConversationDetailWidget` (future) | Not yet |
| Feedback form | `FeedbackDialog` (future) | Not yet |
| AI suggestion | `SuggestionDialog` (future) | Not yet |
| Admin overview | `AdminWindow` (future) | Not yet |
| Rules / users / prompts | Admin sub-widgets (future) | Not yet |
| Training / model health | `TrainingWidget` (future) | Not yet |
| Signal inspector / audit | `DiagnosticsWidget` (future) | Not yet |

### Screens to migrate first (slice 1)
1. Login — auth required for everything else
2. Inbox list — core daily workflow
3. Conversation detail — core daily workflow

### Screens to defer (slice 2+)
- Admin screens (complex, low daily frequency)
- Training/model health (background-only interaction)
- Signal inspector (diagnostic only)

---

## Folder structure

```text
replyright_core/        Framework-neutral models, service interfaces, adapters
replyright_qt/          PySide6 application code only
  main_qt.py            CLI entry point — no pywebview, no FastAPI
  windows/              Top-level QMainWindow/QDialog subclasses
  widgets/              Reusable QWidget subclasses
  viewmodels/           Framework-neutral presentation state (testable without Qt)
  resources/            Icons, stylesheets, compiled Qt resources
```

---

## Service boundary plan

1. `replyright_core` imports nothing from `replyright_qt` or `outlook_dashboard`
2. UI widgets/windows in `replyright_qt` import from `replyright_core` only, with concrete adapters isolated under `replyright_qt/adapters/`
3. Concrete adapters in `replyright_qt/adapters/` or a future `replyright_adapters/` package
   implement the `replyright_core` Protocols by delegating to `outlook_dashboard` modules
4. This keeps intelligence modules stable while the shell changes

---

## Testing plan

- `tests/test_pyside6_scaffold.py` — no browser-engine imports in scaffold
- `tests/test_pyside6_no_browser_engine.py` — comprehensive no-engine checks
- `tests/test_migration_docs_reference_no_qwebengine.py` — docs assertions
- All viewmodel tests use no PySide6 — just pure Python dataclass state
- Qt window tests use `pytest-qt` (future) when PySide6 is in requirements
- Existing 471+ tests must continue to pass throughout migration

---

## Packaging risks and mitigations

| Risk | Mitigation |
|---|---|
| PySide6 adds ~200 MB to installer | Keep PySide6 out of production requirements until slice 1 is demo-ready; evaluate bundle size before committing |
| Qt platform plugin missing on target Windows | Test PyInstaller PySide6 bundle on a clean Windows 10/11 VM before release |
| Qt dark theme inconsistency across Windows versions | Use explicit QPalette rather than relying on system theme |
| Two entry points (run_desktop.py + main_qt.py) in installer | Separate build scripts; ship one or the other per release, not both |
| pywebview removal breaks v0.1.1 smoke test | Do not remove pywebview from production until native slice passes full parity checklist |

---

## What not to touch during migration

- `outlook_dashboard/` intelligence modules (preserve as-is; extract through interfaces)
- `run_desktop.py` production bridge behavior; only the explicit `--native` development flag should touch native scaffold launch
- `installer/` files (release process; separate concern)
- `.github/workflows/` (CI; separate concern)
- `app/` (inactive Next.js scaffold; remains inactive)
- `replyright_kernel/` (experimental; remains experimental)

---

## Acceptance Criteria for First Native Slice (v0.2.0 gate)

1. `replyright_qt/main_qt.py` starts without FastAPI or pywebview
2. Does not import `QWebEngineView`
3. Does not import pywebview
4. Login window appears — native Qt widgets, no browser
5. Successful Supabase auth shows the inbox list
6. Conversation list loads from local SQLite through `InboxServiceProtocol`
7. Read-only Outlook posture preserved (no reply sending from Qt app)
8. All existing 471+ tests still pass
9. New Qt viewmodel unit tests added (no PySide6 dependency in those tests)
10. PyInstaller + Inno Setup build tested on clean Windows VM
