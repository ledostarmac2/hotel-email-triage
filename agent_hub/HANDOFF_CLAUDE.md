# Handoff: Claude

Last updated: 2026-05-18

## What Claude is working on

### Active: PySide6 migration scaffold and planning

Claude owns the PySide6 migration architecture. v0.1.1 security work is complete
and blocked only on the Gemini verdict — Claude is not involved in that path.

**Completed this session:**
- Created `agent_hub/` with all coordination files
- Expanded `replyright_core/models/` — email and user dataclasses
- Expanded `replyright_core/services/` — service Protocol interfaces
- Expanded `replyright_core/adapters/` — adapter Protocol
- Expanded `replyright_qt/windows/` — login and main window skeletons
- Expanded `replyright_qt/viewmodels/` — inbox viewmodel skeleton
- Expanded `replyright_qt/widgets/` — conversation list widget skeleton
- Updated `docs/PYSIDE6_MIGRATION_PLAN.md` — fuller modules/testing/packaging detail
- Added `tests/test_pyside6_no_browser_engine.py` — comprehensive no-engine checks
- Added `tests/test_agent_hub_exists.py` — hub file existence
- Added `tests/test_migration_docs_reference_no_qwebengine.py` — docs assertions
- All tests passing

---

## Claude's next tasks (after v0.1.1 clears)

**Priority 1: First runnable native login slice**
- Wire `replyright_core/services/auth_service.py` to a real adapter
- Build a concrete `replyright_qt/windows/login_window.py` using Qt widgets
- Show the window, accept email/password, call Supabase auth, show error or proceed
- Target: app starts without FastAPI, pywebview, or localhost

**Priority 2: Inbox list window**
- Implement `replyright_core/services/inbox_service.py` adapter against local SQLite
- Build `replyright_qt/windows/main_window.py` with a conversation list
- Use Qt item models (QAbstractListModel) for the conversation table

**Priority 3: Packaging**
- Add PySide6 to a separate `requirements-qt.txt` (not production requirements until ready)
- Validate PyInstaller + PySide6 packaging: check bundle size, Qt platform plugins, icon
- Only merge into production requirements when the native slice is demonstrably runnable

---

## Standing constraints for Claude

- Do not touch `outlook_dashboard/`, `run_desktop.py`, or installer files during PySide6 work
- Do not add QWebEngineView to any file in `replyright_qt/`
- Do not import pywebview in `replyright_qt/`
- Do not wire `replyright_core/` into production until a runnable slice exists
- Do not commit real secrets
- Do not log raw email bodies
- Do not add reply sending
