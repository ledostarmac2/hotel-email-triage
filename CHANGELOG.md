# Changelog

All notable changes to ReplyRight are documented here.

## [Unreleased] — 2026-05-19

### Features

- **KYC Inspections sidebar module** — built-in reminder system for hotel inspection compliance. Tracks events through `pending → acknowledged/snoozed → completed/skipped` lifecycle. Qt panel polls every 3 seconds (only when visible), shows countdown to next inspection, supports strict-mode mandatory acknowledgement dialog. Team member selector for completion attribution.
- **PySide6 native shell** (`replyright_qt/`) — full native Qt UI. FastAPI backend starts first, then the Qt window opens via `ApiClient`. Includes login window, sidebar nav, conversation list/detail splitter, admin panel, and KYC panel. The `--native` flag is accepted but is now a no-op (Qt is the default).

### Auth

- Local SQLite users now checked first in `authenticate_user`; Supabase is an optional fallback for cloud-only users. Fixes login failures where a valid Supabase JWT was returned but the local account was never reached.
- `ensure_admin()` runs at startup whenever `REPLYRIGHT_ADMIN_EMAIL` + `REPLYRIGHT_ADMIN_PASSWORD` are set — seeds or repairs the admin account immediately on launch.
- First-run setup can create a local admin without requiring Supabase API keys.

### Repo Cleanup

- `agent_hub/` renamed to `docs/coordination/` — 12 coordination files, git history preserved.
- Root planning docs archived to `docs/archive/planning/`; stale migration docs to `docs/archive/migration/`.
- `app/` (inactive Next.js scaffold) untracked from git and added to `.gitignore`.
- `reference/` (3,076 third-party files) untracked from git via `git rm -r --cached`.
- `dist2/ReplyRight.exe` and `new_dependencies.txt` removed.
- `docs/PROJECT_STRUCTURE.md` added — documents root contract and active/inactive path policy.
- `run.bat` and `setup.ps1`: Python 3.11 → 3.12 references; `setup.ps1` exe path corrected to `dist\ReplyRight\ReplyRight.exe`.

### CI / Build

- `.github/workflows/build.yml`: empty-string placeholders for unused secrets instead of `${{ secrets.X }}` references. Required-key verify list trimmed to the 5 keys actually needed.
- `v0.1.1` retag to `88acd29` after auth and release fixes landed.

## [0.1.1] — 2026-05-18

### Summary

- Security cleanup: `bundled_secrets.py` emptied, `/credentials-setup` flow added, `installer/sample.env` introduced.
- Auth fallback: local SQLite users as fallback when Supabase is unavailable or unconfigured.
- Release pipeline fixes: installer rename idempotency, CI .env packaging, admin seed on startup.

## [0.1.0] — 2026-05-17

### Summary

Phases 1-6 complete. ReplyRight is a fully functional, read-only Outlook email intelligence dashboard for the Waldorf Astoria New York reservations shared inbox (NYCWA_Reservations). The app runs as a local FastAPI + pywebview desktop application with 160 passing automated tests and zero open failures.

---

### Features (Phases 1-6)

**Phase 1 — Outlook import**
- Read-only `pywin32` COM import from `NYCWA_Reservations > Inbox`
- Microsoft Graph OAuth as optional fallback (shared and personal mailbox modes)
- Duplicate prevention by Graph message ID
- Local SQLite email storage with stale-row cleanup
- VBA macro fallback (`ExportNYCWAReservationsInboxOnly`) for environments without direct COM access

**Phase 2 — Local triage**
- Conversation-level urgency scoring (1-5 scale, conservative — 5 reserved for same-day blockers or serious risk)
- Category classification (14 categories: VIP pre-arrival, Billing dispute, Rooming list/group, Accessibility request, etc.)
- Sentiment detection with quoted-reply isolation (old upset text does not override friendly latest reply)
- Owner routing: Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, All Departments
- Contact type detection: Internal, Group contact, Travel agency, Direct guest
- Next steps and missing information extraction
- Risk flag detection (Billing, Legal, VIP, Media/PR, ADA, Overbooking, Safety)
- Confidence scoring (10-95%) with color-coded pill in UI
- CCA/form-submission routing to Reservations with completion steps

**Phase 3 — AI classification**
- OpenAI (`gpt-5.4-nano`) refresh classification when key configured
- Google Gemini (AI Studio) fallback when OpenAI unavailable
- Anthropic Claude on-demand reply draft for selected email
- Local heuristic triage always available as final fallback
- PII redaction before all external AI calls: Luhn-valid card numbers, CVV, expiry phrases, email addresses, phone numbers, payment links, confirmation numbers
- Accurate payment-link redaction count (redaction now runs before URL-strip in classification payload)

**Phase 4 — Adaptive feedback**
- `triage_feedback` table stores per-conversation corrections (urgency, owner, category, contact type, sentiment, status, summary quality 1-5, reply quality 1-5)
- `POST /api/emails/{email_id}/feedback` applies corrections immediately
- Rule candidate engine mines recurring patterns — 3 corrections create a visible candidate, 5+ auto-promote to shared rule
- Admin `Reject` / `Dismiss` controls for rule candidates
- Supabase feedback upload with local retry queue on next startup
- Supabase approved rules cached durably in SQLite for offline use
- Known sender domain mappings applied during local triage

**Phase 5 — Semantic Kernel orchestration**
- `replyright_kernel/` package with three Semantic Kernel plugins:
  - `PriorityTriagePlugin` — structured urgency + category + owner + sentiment triage
  - `ExecutiveSummaryPlugin` — concise executive summary with action items and risk flags
  - `AuditCompliancePlugin` — audit-ready compliance event log entries
- `ReplyrightEngine` orchestrates plugins in sequence with a single kernel instance
- Prompt versions downloaded from Supabase and cached locally

**Phase 6 — Testing**
- 160 pytest tests, 0 failures
- Test files: `test_redaction.py` (40), `test_malformed_emails.py` (37), `test_kernel_plugins.py` (43), `test_kernel_orchestration.py` (18), `test_ai_and_database.py` (14), `test_api_workflow_pytest.py` (3), `test_business_logic_pytest.py` (4), `test_import_smoke.py` (1)
- Full PII redaction pipeline tested: Luhn, card, CVV, expiry, email, phone, payment links, confirmation numbers
- Malformed/empty/oversized/unicode/HTML/reply-thread edge cases covered
- FastAPI routes tested with TestClient and mocked external services
- Semantic Kernel plugins and end-to-end orchestration tested with mocked LLM
- No live credentials, no live Outlook, no live Supabase in any test

---

### Bug Fixes

- **Redaction order** (`ai.py _refresh_classification_payload`): `latest_message_text()` was stripping URLs before `redact_sensitive_text()` ran, causing `counts["payment_links"]` to always be 0. Fixed: redact first, then clean/truncate.
- **Category priority** (`ai.py _category_for`): "billing" check fired before "rooming list" for external senders. Group emails routinely say "billing instructions" but mean rooming logistics, not a dispute. Fixed: explicit "rooming list" check inserted before billing check.
- **Dead category check** (`ai.py _category_for`): Redundant `"rooming list" in text` condition at the secondary group/block check was unreachable after the above fix. Removed; `"group"` and `"block"` signals preserved.

---

### Code Optimizations

- **`auth.py`**: Extracted `_send_via_smtp()` helper to eliminate ~15 lines of duplicated SMTP connection code shared between `send_invite_email` and `send_reset_email`.
- **`supabase_client.py`**: Extracted `_download_and_cache()` to replace three near-identical 30-line download functions (`download_approved_rules`, `download_prompt_versions`, `download_known_senders`). Eliminated per-iteration `httpx.Client` creation inside `promote_rule_candidates` loop — client now created once and reused.
- **`main.py`**: Moved `secrets` from a local function import (`import secrets as _sec` inside `api_invite`) to a top-level module import. Added TTL pruning of stale `_RATE_LIMIT_BUCKETS` keys to prevent unbounded dict growth on long-running servers.
- **`registry.py`**: Replaced three identical `kernel.add_plugin()` + `logger.debug()` blocks with a data-driven loop over `_PLUGINS`. Removed large boilerplate comment blocks for future tiers (intent preserved in `docs/DECISIONS.md` and `docs/ARCHITECTURE.md`).
- **`ai.py`**: Wrapped bare `message.content[0].text` / `json.loads()` in `_analyze_with_claude` with a `try/except (IndexError, json.JSONDecodeError)` that raises a descriptive `ValueError` instead of crashing with an opaque traceback.

---

### Security

- `SUPABASE_URL` and `SUPABASE_KEY` values shared in session chat have been flagged for rotation before live use.
- `GOOGLE_AI_API_KEY` shared in session chat has been flagged for rotation before live use.
- No raw guest PII (bodies, reservation numbers, payment details, attachments) is written to any Supabase training table. Phase 7 must pass through a sanitize-and-review pipeline before any training data leaves the local machine.
- ReplyRight remains strictly read-only: no send, delete, archive, move, category, or mark-read actions against Outlook.

---

### What Is Not In This Release (Phase 7)

Phase 7 — local hotel-specific classifier training — is staged and documented but not started. See `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` for the full specification.

Targets for Phase 7:
1. Import historical completed emails from Outlook
2. Redact and sanitize PII from training examples
3. AI-label sanitized examples; human-review samples
4. Store sanitized training dataset in Supabase (no raw PII)
5. Train lightweight local classifiers for urgency, owner, category, status, missing-information, reply-required, escalation-required
6. Route by confidence: use local classifier for high-confidence decisions, fall back to external AI for low-confidence or complex/sensitive tasks
7. Reserve external AI (OpenAI/Claude) for summary, reply-drafting, and low-confidence edge cases only
