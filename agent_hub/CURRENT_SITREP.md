# Current Situation Report

Last updated: 2026-05-18 (Session 4)

## Status: PySide6 Merged into main | Admin Dashboard In Progress

---

## What is done

### PySide6 Phase 1 — native Qt shell (committed 493803e on feat/pyside6-native-ui)

- `pywebview` + `pythonnet` removed from `requirements.txt`; `PySide6>=6.7` added
- `run_desktop.py`: `_open_window` (WebView2) → `_open_qt_window` (native Qt)
- Full native UI written: `api_client.py`, `app.py`, `styles/theme.py`,
  `sidebar_nav.py`, `filter_bar.py`, `conversation_list.py`,
  `conversation_detail.py`, `login_window.py`, `main_window.py`
- FastAPI backend **untouched** — Qt shell calls same HTTP endpoints
- 485 tests passing, 0 failures on branch

### v0.1.1 source work (committed ea84602 on main)
- `bundled_secrets.py` cleaned: no `SUPABASE_SERVICE_ROLE_KEY`, no `ANTHROPIC_API_KEY`,
  no `OPENAI_API_KEY`, no XOR obfuscation. `_SECRETS` dict is empty.
- `needs_credentials_setup()` added to `auth.py`: returns `True` when either
  `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` is absent or blank.
- `write_local_env()` added to `config.py`: atomic `.env` merge + immediate env injection.
- `/credentials-setup` route added to `main.py`: GET renders form; POST validates and
  writes `.env`; both redirect appropriately.
- `credentials_setup.html` added to `outlook_dashboard/static/`: dark-theme, no
  hardcoded secrets, no JWT-prefix placeholders.
- `installer/sample.env` added: ships in installer; all secret fields empty.
- `scripts/check_no_bundled_secrets.py` added: static checker for CI.
- `tests/test_secret_hygiene.py` added: 14 assertions.
- All test files updated. **471 tests passing, 0 failures.**

### PySide6 migration scaffold (committed)
- `replyright_core/` — models, services, adapters, app_state.py
- `replyright_qt/` — main_qt.py, windows, widgets, viewmodels, resources
- `docs/PYSIDE6_MIGRATION_PLAN.md` — full migration plan
- `tests/test_pyside6_scaffold.py` — no-browser-engine assertions

### Agent coordination
- `agent_hub/` created with all coordination files
- `tests/test_agent_hub_exists.py` — existence assertions
- `tests/test_pyside6_no_browser_engine.py` — expanded browser-engine checks
- `tests/test_migration_docs_reference_no_qwebengine.py` — docs assertions

---

## What is blocked

| Blocker | Owner | Resolution |
|---|---|---|
| Codex rate-limited | Codex | Rate limit resolves on its own |

---

## What is next (in order)

1. Build Qt Admin Dashboard panel (`admin_panel.py`)
2. Verify PyInstaller PySide6 packaging (`build_exe.ps1`)
3. Update testing docs for native Qt assertions

---

## Do not do (standing orders)

- Do not tag v0.1.1 before Gemini verdict
- Do not bundle `.env` in the installer
- Do not put `SUPABASE_SERVICE_ROLE_KEY` in `bundled_secrets.py`
- Do not put `ANTHROPIC_API_KEY` in `bundled_secrets.py`
- Do not add reply sending
- Do not log raw email bodies
- Do not weaken PII redaction
- Do not touch `app/` (inactive Next.js scaffold)
- Do not wire `replyright_kernel/` into production
- Do not use `QWebEngineView`, pywebview, Electron, or Tauri in the new Qt app
