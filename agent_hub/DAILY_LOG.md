# Daily Log

Append-only log. Most-recent entry first.

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
