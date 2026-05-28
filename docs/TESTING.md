# ReplyRight Testing Guide

Last updated: 2026-05-28

## Primary Commands

Run the full suite the same way Codex and release-prep tasks do:

```powershell
python -m pytest tests/ -x --timeout=60 -q --no-header
```

Useful focused runs:

```powershell
python -m pytest -m unit tests/ -q --timeout=60
python -m pytest -m integration tests/ -q --timeout=60
python -m pytest -m ui tests/ -q --timeout=60
python -m pytest -m safety tests/ -q --timeout=60
python -m pytest -m "not slow" tests/ -q --timeout=60
```

Run a specific file or test:

```powershell
python -m pytest tests/test_recommended_action.py -q --timeout=60
python -m pytest tests/test_v1_features.py::TestSidebarNeedsReviewQueue -q --timeout=60
```

Collect tests without running them:

```powershell
python -m pytest --collect-only -q tests/
python -m pytest --collect-only -q -m ui tests/
```

Coverage report:

```powershell
python -m pytest tests/ --cov=outlook_dashboard --cov=replyright_qt --cov=replyright_kernel --cov-report=term-missing
```

## Pytest Markers

Markers are registered in `pytest.ini` and applied in `tests/conftest.py` by file.

| Marker | Use |
|---|---|
| `unit` | Fast isolated tests with no live services or repo runtime writes. |
| `integration` | Local multi-module or FastAPI route tests with mocked services. |
| `ui` | Native desktop/UI contract tests; no browser engine or live Outlook. |
| `slow` | Broad scans or high-volume scenario suites. |
| `safety` | Read-only Outlook, secrets, privacy, error-hardening, and no-external-AI guardrails. |

## Test Groups

### Recommended Action And Queues

- `tests/test_recommended_action.py`: deterministic action routing, taxonomy completeness, operational queue filtering, and realistic hotel scenarios.
- `tests/test_safety_regression.py`: safety contracts proving recommended-action and queue metadata stay deterministic and metadata-only.
- `tests/test_v1_features.py`: API-client queue mapping, sidebar queue labels/order, and schema compatibility.

Overlap is intentional here: unit tests prove routing decisions, safety tests prove boundaries, and v1 tests prove UI/API wiring.

### Safety And Privacy

- `tests/test_safety_guardrails.py`: Outlook read-only contract, no auto-send, no external AI in guarded paths, PII handling.
- `tests/test_secret_hygiene.py`: source and payload secret hygiene.
- `tests/test_installer_contract.py`: installer payload exclusions and runtime dependency contracts.
- `tests/test_config_contract.py`: centralized access to guarded environment variables.
- `tests/test_platform_guards.py`: optional Windows/COM imports remain lazy.
- `tests/test_error_hardening.py`: plain-English API/UI errors and internal diagnostic logging.
- `tests/test_privacy_hygiene.py`: no tracked runtime data, no tracked labeling exports, doc password hygiene, and training-data redaction.

Normal source secret scans intentionally ignore local ignored build output such as `dist/`; release payload audits scan staged build output explicitly.

### UI And Desktop

- `tests/test_pyside6_no_browser_engine.py`: native PySide6 shell contract, no `QWebEngineView`, display labels, theme guardrails.
- `tests/test_pyside6_scaffold.py`: native scaffold imports and window availability.
- `tests/test_desktop_startup.py`: startup health-gate contracts without launching live Outlook.
- `tests/test_first_run_setup.py`: first-run setup API/native workflow contracts.
- `tests/test_migration_docs_reference_no_qwebengine.py`: docs and migration contract for native UI.

### API And Integration

- `tests/test_api_workflow_pytest.py`, `tests/test_api_full_coverage.py`: FastAPI workflows with synthetic payloads and mocked external services.
- `tests/test_auth_supabase.py`: Supabase Auth request construction with mocked network calls.
- `tests/test_diagnostics_contract.py`: deployment/system status response shape.
- `tests/test_kyc_backend.py`, `tests/test_kyc_service_full.py`: KYC service and API behavior with local temp databases.
- `tests/test_training_pipeline.py`, `tests/test_completed_training_pipeline.py`, `tests/test_labeling_workflow.py`: sanitized training/export workflows.

## Isolation Rules

- Unit tests must not contact live Outlook, live Supabase, OpenAI, Google AI, Claude, SMTP, or Microsoft Graph.
- `tests/conftest.py` clears live AI/Supabase environment variables by default. Tests that need configured values must set fake values and mock the network boundary.
- Tests that touch SQLite should use `tmp_path`, `tmp_db`, or `app_client`; do not write local databases under repo `data/`.
- Tests must not create `.env`, `.sqlite3`, `.msg`, build output, packaged binaries, or raw mailbox exports in tracked repo paths.
- Synthetic email fixtures must not include real guest data, real reservation IDs, payment card data, live message IDs, or full sender addresses from production mailboxes.

## What Is Not Covered By Unit Tests

- Live classic Outlook COM import against the shared mailbox.
- Live Microsoft Graph OAuth against a tenant.
- Live Supabase schema and Auth behavior beyond mocked request contracts.
- Live OpenAI, Google AI, or Claude generation.
- Installer install/uninstall on a clean Windows machine.

Use manual smoke testing and release workflow checks for those paths.
