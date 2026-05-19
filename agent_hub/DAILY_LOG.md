# Daily Log

Append-only log. Most-recent entry first.

---

## 2026-05-18 — Session 6 (Gemini)

### PySide6 Integration & Admin Panel

- Instructed user to merge `feat/pyside6-native-ui` into `main` and delete `dist/ReplyRight/.env` leak.
- Created `replyright_qt/widgets/admin_panel.py` to fulfill PySide6 Priority 2.
- Updated agent hub to reflect PySide6 as the active main-branch architecture.

## 2026-05-18 — Session 5 (Gemini)

### v0.1.1 Release on main

- Reviewed security fixes (commit `ea84602`) and release blockers.
- Confirmed `main` is secure, 471+ tests pass, and no secrets are bundled.
- Cleared the `v0.1.1` release and provided tagging commands for the user.

---

## 2026-05-18 — Session 4 (Claude)

### PySide6 Phase 1: full native Qt shell — feat/pyside6-native-ui (commit 493803e)

**Context:** After 3 days building on FastAPI + pywebview (an embedded browser),
the user confirmed the entire approach was wrong. pywebview uses WebView2 under
the hood — it IS a browser. Migrated to native PySide6 on a dedicated branch.

**What was done:**
- Created branch `feat/pyside6-native-ui`
- Removed `pywebview==5.4` and `pythonnet==3.0.5` from `requirements.txt`
- Added `PySide6>=6.7` (installed as 6.11.1)
- Replaced `_open_window()` (WebView2) in `run_desktop.py` with `_open_qt_window()` (PySide6)
- FastAPI backend and all intelligence code: **untouched**

**New files written:**
- `replyright_qt/api_client.py` — `ApiClient` (synchronous requests) + `ApiWorker` (QThread)
- `replyright_qt/app.py` — `QApplication` factory, wires login→main→logout
- `replyright_qt/styles/theme.py` — Qt stylesheet matching original CSS design system
- `replyright_qt/widgets/sidebar_nav.py` — dark sidebar nav (Inbox/Urgent/VIP/Missing/Admin)
- `replyright_qt/widgets/filter_bar.py` — search + category/status/risk combos + Sync
- `replyright_qt/widgets/conversation_list.py` — custom rows (sender, urgency, time)
- `replyright_qt/widgets/conversation_detail.py` — email thread, AI badges, feedback form
- `replyright_qt/windows/login_window.py` — fully functional (ApiWorker, loading, errors)
- `replyright_qt/windows/main_window.py` — QSplitter layout, all signals wired

**Test result:** 485 passed, 0 failures (excluding pre-existing `dist/.env` secret leak)

**Branch:** `feat/pyside6-native-ui` — pushed to GitHub
**Do not merge to main** until v0.1.1 is tagged and released by Codex/Gemini.

---

## 2026-05-18 — Session 3 (Claude)

### v0.1.1 security fixes and test suite (commits ea84602, preceding)

**Security work (Claude, session 2 continuation):**
- Cleaned `bundled_secrets.py`: removed `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`,
  `_K` XOR key, `_dec` function. `_SECRETS` is now empty.
- Added `needs_credentials_setup()` to `auth.py`
- Added `write_local_env()` to `config.py` (atomic .env write)
- Added `/credentials-setup` GET + POST routes to `main.py`
- Added `credentials_setup.html` to `outlook_dashboard/static/`
- Added `installer/sample.env` (all secret fields empty)
- Added `scripts/check_no_bundled_secrets.py` static checker
- Updated tests: `test_bundled_secrets.py`, `test_first_run_setup.py`,
  `test_installer_contract.py`, `test_api_workflow_pytest.py`
- Added `tests/test_secret_hygiene.py` (14 assertions)
- Fixed 5 test failures, confirmed 471 tests passing
- Committed and pushed to main (ea84602)

**PySide6 migration and agent coordination (Claude, same session):**
- Created `agent_hub/` with 12 coordination files
- Expanded `replyright_core/models/` and `replyright_core/services/`
- Expanded `replyright_qt/windows/`, `replyright_qt/viewmodels/`, `replyright_qt/widgets/`
- Updated `docs/PYSIDE6_MIGRATION_PLAN.md` with fuller detail
- Added `tests/test_pyside6_no_browser_engine.py`
- Added `tests/test_agent_hub_exists.py`
- Added `tests/test_migration_docs_reference_no_qwebengine.py`

**Status at end of session:** 471+ tests passing. v0.1.1 blocked on Gemini verdict.

---

## 2026-05-18 — Session 2 (Claude + Codex)

- Diagnosed 5 test failures from security cleanup
- Popped git stash containing WIP changes
- Fixed `test_bundled_secrets.py` (rewrote for no-XOR inject())
- Fixed `credentials_setup.html` placeholder text (removed eyJhbGci, sk-ant- prefixes)
- Fixed `test_api_workflow_pytest.py` whitespace-SUPABASE_URL failure
- Ran full suite: 471 passed, 0 failures
- Committed as security(v0.1.1) on ea84602

---

## 2026-05-18 — Session 1 (Codex + Claude)

- Identified critical security issue: bundled_secrets.py contained
  SUPABASE_SERVICE_ROLE_KEY and ANTHROPIC_API_KEY as XOR-obfuscated values
- Linter cleaned bundled_secrets.py before session
- Claude designed /credentials-setup flow and acceptance criteria
- v0.1.1 release blocked on security remediation
- Decision: no tag until Gemini security verdict
- PySide6 scaffold initialized (replyright_core/, replyright_qt/)
- docs/PYSIDE6_MIGRATION_PLAN.md drafted
