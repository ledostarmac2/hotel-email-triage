# ReplyRight — Testing Guide

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Test runner | pytest 9.x | Unified runner for all test types |
| Coverage | pytest-cov | Line/branch coverage reports |
| Async support | pytest-asyncio | `async def` test functions (kernel orchestration) |
| HTTP assertions | httpx + FastAPI TestClient | FastAPI route tests without a live server |
| HTML parsing | beautifulsoup4 | Dashboard shell structure assertions |

Legacy `unittest` test classes run automatically through pytest's built-in discovery.

## Commands

### Run all tests
```powershell
python -m pytest tests/
```

### Verbose output
```powershell
python -m pytest tests/ -v
```

### Coverage report (terminal)
```powershell
python -m pytest tests/ --cov=outlook_dashboard --cov=replyright_kernel --cov-report=term-missing
```

### Coverage report (HTML — open dist/htmlcov/index.html)
```powershell
python -m pytest tests/ --cov=outlook_dashboard --cov=replyright_kernel --cov-report=html:dist/htmlcov
```

### Run a specific file
```powershell
python -m pytest tests/test_redaction.py -v
```

### Run a specific test class or function
```powershell
python -m pytest tests/test_redaction.py::TestCardRedaction -v
python -m pytest tests/test_malformed_emails.py::TestUrgencyBoundaries::test_legal_threat_urgency_is_maximum -v
```

### Legacy unittest runner (still works, useful for CI comparison)
```powershell
python -m unittest discover -s tests
```

## Test Files

| File | Count | Coverage area |
|---|---|---|
| `test_ai_and_database.py` | 14 | Core triage logic, database, auth, adaptive feedback, rule candidates, Supabase cache |
| `test_import_smoke.py` | 1 | All active Python modules import cleanly |
| `test_business_logic_pytest.py` | 4 | PII redaction pipeline, category classification, malformed email baseline |
| `test_api_workflow_pytest.py` | 3 | FastAPI routes end-to-end: import, list, detail, analyze, feedback, admin stats, rate limit |
| `test_redaction.py` | 40 | Luhn validation, card/CVV/expiry/email/phone/payment-link/confirmation-number redaction |
| `test_malformed_emails.py` | 37 | Empty/None/malformed inputs, oversized text, unicode, HTML, reply thread isolation, urgency bounds |
| `test_kernel_plugins.py` | 43 | PriorityTriagePlugin, ExecutiveSummaryPlugin, AuditCompliancePlugin |
| `test_kernel_orchestration.py` | 18 | End-to-end kernel pipeline with mocked LLM |
| **Total** | **160** | |

## Key Design Rules

- **No real credentials**: all tests set `OPENAI_API_KEY=""`, `ANTHROPIC_API_KEY=""`, `GOOGLE_AI_API_KEY=""`, `SUPABASE_URL=""`.
- **No live Outlook**: inbox tests use the `POST /api/outlook-desktop/import-json` route with synthetic payloads.
- **No live Supabase**: Supabase upload/download calls are no-ops when `SUPABASE_URL` is empty.
- **Isolated databases**: every test that touches SQLite uses a `tmp_path`-scoped temporary database.
- **Mocked LLM**: kernel orchestration tests patch the kernel's `invoke_prompt` with a `MagicMock`.
- **Deterministic**: no random seeds, no timing dependencies, no network calls.

## Shared Fixtures (conftest.py)

| Fixture | Scope | What it provides |
|---|---|---|
| `tmp_db` | function | Fresh initialized SQLite at `tmp_path/test.sqlite3` |
| `plain_email` | function | Minimal email dict, no urgency signals |
| `urgent_email` | function | Same-day + VIP + accessibility + follow-up signals |
| `complaint_email` | function | Legal threat language, high urgency |
| `cca_completion_email` | function | Completed CCA form — low urgency, Reservations owner |
| `accessibility_email` | function | ADA request — ADA risk flag expected |
| `thread_with_quoted_upset` | function | Outlook thread with positive latest reply over upset quoted history |
| `app_client` | function | Authenticated FastAPI TestClient (admin login, temp DB, no external AI) |

## Coverage Targets

Run with `--cov-report=term-missing` to see uncovered lines. Current focus areas:

| Module | Notes |
|---|---|
| `outlook_dashboard/redaction.py` | Fully covered by `test_redaction.py` |
| `outlook_dashboard/ai.py` | Core triage covered; OpenAI/Gemini/Claude branches require API key |
| `outlook_dashboard/database.py` | Core paths covered; admin analytics covered via `app_client` |
| `outlook_dashboard/auth.py` | Login, admin repair, session management covered |
| `replyright_kernel/plugins/` | All three plugins fully covered |
| `replyright_kernel/engine.py` | Covered with and without API key |

## What Is Not Tested Here

- Live Microsoft Graph OAuth flow (requires Entra app registration + real tenant)
- Live Outlook COM import (requires classic Outlook for Windows + pywin32 accessible mailbox)
- Live OpenAI/Gemini/Claude draft generation (requires real API key and incurs cost)
- Live Supabase upload/download (requires `SUPABASE_URL`/`SUPABASE_KEY` and live schema)
- pywebview desktop window rendering (requires WebView2 runtime, not a unit test concern)

These paths should be tested manually using the instructions in `docs/CURRENT_STATE.md`.

## Phase 7 Testing Considerations

When local classifier training is added (Phase 7), the following test categories will be needed:

- Sanitized training record creation (verify PII is stripped before Supabase storage)
- Feature extraction from email → classifier input vector
- Classifier prediction output validation (schema, score ranges)
- Confidence threshold routing (high → local predict, low → external AI)
- Model activation/rollback round-trip (activate new version, verify it loads, rollback)
- Admin metrics endpoint correctness

No raw guest email bodies, reservation numbers, or payment details should appear in any test fixture or training record.
