# PySide6 Migration — Hub Summary

Last updated: 2026-05-18

Full plan: `docs/archive/migration/PYSIDE6_MIGRATION_PLAN.md`

---

## Decision

ReplyRight will migrate to a PySide6 native desktop shell for v0.2.0.
The pywebview bridge remains only until the native shell reaches parity.

**Non-negotiable rules:**
- No `QWebEngineView` — ever
- No `pywebview` in the new app shell
- No Electron, no Tauri, no other browser/WebView engine as the primary UI
- Native Qt widgets only

---

## Current scaffold state (as of 2026-05-18)

| Path | State | Description |
|---|---|---|
| `replyright_core/app_state.py` | Skeletal | AppState dataclass |
| `replyright_core/models/email_models.py` | Skeletal | Conversation, EmailMessage, TriageResult dataclasses |
| `replyright_core/models/user_models.py` | Skeletal | User dataclass |
| `replyright_core/services/auth_service.py` | Skeletal | AuthServiceProtocol |
| `replyright_core/services/inbox_service.py` | Skeletal | InboxServiceProtocol |
| `replyright_core/adapters/sqlite_adapter.py` | Skeletal | SqliteAdapterProtocol |
| `replyright_qt/main_qt.py` | Guarded placeholder | Raises RuntimeError if run |
| `replyright_qt/windows/login_window.py` | Skeletal | LoginWindow (QWidget subclass) |
| `replyright_qt/windows/main_window.py` | Skeletal | MainWindow (QMainWindow subclass) |
| `replyright_qt/viewmodels/inbox_viewmodel.py` | Skeletal | InboxViewModel with signal stubs |
| `replyright_qt/widgets/conversation_list.py` | Skeletal | ConversationListWidget stub |

**All scaffold files:** no QWebEngineView, no pywebview, no Electron, no Tauri.

---

## What the bridge still does (pywebview + FastAPI)

The production app path is:
```
run_desktop.py -> FastAPI (outlook_dashboard/main.py) -> static HTML/CSS/JS -> pywebview window
```

This path stays unchanged until the first native Qt slice is runnable.

---

## Next milestone: First Native Slice

Acceptance criteria:
1. `replyright_qt/main_qt.py` starts without FastAPI or pywebview
2. Shows a login window (Qt native widget, no browser)
3. Authenticates against Supabase via `replyright_core/services/auth_service.py`
4. On success: shows inbox list loaded from local SQLite
5. Does not import `QWebEngineView`
6. Does not import `pywebview`
7. All existing 471+ tests still pass
8. New Qt service/viewmodel tests added

Owner: Claude
Dependency: v0.1.1 must be tagged and stable before this work begins
