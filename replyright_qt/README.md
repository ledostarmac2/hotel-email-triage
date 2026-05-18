# ReplyRight Qt

This is the scaffold for the planned PySide6 native desktop migration.

It is not production-wired yet. The current app remains `outlook_dashboard/` plus `run_desktop.py`.

## Native UI Rules

- Use PySide6 widgets and models.
- Do not use `QWebEngineView` as the main shell.
- Do not import pywebview.
- Do not use Electron, Tauri, or another browser/WebView shell.
- Reuse `replyright_core` services as they are extracted.
- Preserve local-first behavior, read-only Outlook access, and human review gates.

## Planned Screen Map

| Current FastAPI/JS Screen | Future Qt Area |
| --- | --- |
| Login | `windows/login_window.py` |
| First-run setup | `windows/setup_window.py` |
| Inbox queue | `widgets/conversation_list.py` |
| Email detail/thread | `widgets/conversation_detail.py` |
| Feedback form | `widgets/feedback_panel.py` |
| AI suggestion modal | `widgets/reply_suggestion_dialog.py` |
| Admin overview | `windows/admin_window.py` |
| Rules/admin users | `widgets/admin_rules.py`, `widgets/admin_users.py` |
| Training/model health | `widgets/training_panel.py`, `widgets/model_health_panel.py` |
| Diagnostics/update | `widgets/diagnostics_panel.py` |

## Dependency Note

PySide6 is the intended dependency for this package, but it is deliberately not added to production requirements in this scaffold commit. Add it only when the native shell has a runnable slice and packaging has been verified.
