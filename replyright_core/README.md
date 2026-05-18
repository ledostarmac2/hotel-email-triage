# ReplyRight Core

This package is the planned extraction point for reusable ReplyRight application services.

It is intentionally not wired into production yet. The active app remains:

```text
outlook_dashboard/
run_desktop.py
```

## Purpose

Future PySide6 work should move reusable business logic behind service boundaries here while preserving the existing, tested modules in `outlook_dashboard/`.

Initial service extraction targets:

- Authentication/session facade over Supabase Auth helpers
- Inbox import and message repository facade over SQLite and Outlook COM
- Email analysis facade over deterministic triage, local classifier, shared rules, and optional AI
- Feedback/training facade over local SQLite and Supabase training tables
- Updater/diagnostics facade over build metadata, health, and GitHub release checks

## Rules

- No UI framework imports in `replyright_core`.
- No pywebview imports.
- No PySide6 imports.
- No Outlook mutation: no send, delete, archive, move, category, or mark-read behavior.
- No raw email body logging.
- Keep local-first behavior and human review gates.
