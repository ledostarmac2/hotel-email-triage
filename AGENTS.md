# ReplyRight Agent Guide

This repository is the ReplyRight hotel reservations email triage app. Keep the project easy to resume from another computer and preserve the current read-only Outlook safety posture unless Brian explicitly approves a broader workflow.

## Required First Reads

Before making changes, read these files in order:

1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/HANDOFF.md`

Use `docs/CURRENT_STATE.md` as the latest truth. Treat older root-level planning docs as historical unless the current docs say otherwise.

For broad architecture, adaptive learning, Supabase, staged AI pipeline, shared feedback, training, classifier, or admin dashboard work, also read:

5. `docs/ROADMAP.md`
6. `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md`
7. `docs/TRAINING_PIPELINE.md`
8. `docs/CLASSIFIER.md`
9. `docs/SECURITY_AND_PRIVACY.md`
10. `docs/DEPLOYMENT.md`
11. `docs/OPERATIONS_GUIDE.md`
12. `docs/V1_RELEASE_PLAN.md`

## Source Of Truth

- The active runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The Windows executable is built by `build_exe.ps1` and outputs the onedir app `dist\ReplyRight\ReplyRight.exe`.
- User-facing releases are installer-first. The primary GitHub Release asset must be `ReplyRightSetup-v{version}.exe`; raw `dist\ReplyRight\ReplyRight.exe` is an internal build input, not the default download.
- The `app/` directory is an inactive Next.js scaffold that has been untracked from git. Do not migrate logic there unless Brian explicitly asks.
- `replyright_kernel/` is experimental and additive. It is not the active desktop app path.
- `replyright_core/` is a scaffold for shared models/services. `replyright_qt/` is the active PySide6 native UI shell, wired through `run_desktop.py` → FastAPI backend + `ApiClient`.
- The active desktop UI is the native PySide6 shell in `replyright_qt/`; the legacy FastAPI-served static dashboard under `outlook_dashboard/static/` remains available as supporting/admin web UI code.

## Handoff Protocol

After meaningful work:

- Update `docs/CURRENT_STATE.md` with the latest status, risks, and next steps.
- Append a concise entry to `docs/HANDOFF.md` with date, summary, files changed, verification, and remaining work.
- Update `docs/DECISIONS.md` when architecture, runtime, data flow, security posture, or integration strategy changes.
- Update `docs/CHANGELOG_AI.md` for meaningful AI-assisted behavior changes.
- Keep docs and code in sync. Do not leave stale setup, build, or workflow instructions behind.
- Do not store chain-of-thought, private reasoning, credentials, mailbox contents, raw email bodies, or large memory dumps in docs.

## Security And Outlook Rules

- Preserve read-only Outlook behavior. The app may read/import messages and update local SQLite state, but it must not send, delete, archive, move, categorize, mark read, or otherwise mutate Outlook messages without explicit new approval.
- Do not add automatic reply sending.
- Do not remove human review gates for AI drafts, risky classifications, model promotion, rule approval, or future sending workflows.
- Do not log raw email bodies.
- Do not commit `.env`, `dist\ReplyRight\.env`, local SQLite databases, `.msg` exports, build folders, virtual environments, vendored dependencies, startup logs, or packaged EXE binaries.
- Redact payment-like data and other sensitive identifiers before any external AI call or training export.
- Do not weaken PII redaction.
- Do not print secrets, service-role keys, session cookies, mailbox contents, or raw guest data in logs or final responses.

## Architecture Rules

- Preserve local-first operation. ReplyRight should remain useful without OpenAI, Claude, Google AI, or live Supabase.
- Do not require paid AI APIs for baseline classification.
- Keep deterministic logic separate from AI-generated reasoning.
- Keep taxonomy metadata centralized in `outlook_dashboard/taxonomy.py` and `outlook_dashboard/taxonomy_meta.py`.
- Treat Supabase approved rules, prompt versions, known senders, training examples, and feedback events as shared configuration or learning data, not as a live mailbox store.
- Keep the hotel intelligence modules pure unless a later wiring task explicitly changes that:
  - `hotel_entities.py`
  - `travel_programs.py`
  - `urgency_engine.py`
  - `signal_extractor.py`
  - `sender_intelligence.py`
- Preserve Windows and PyInstaller compatibility.
- Preserve installer-first release behavior and the health-gated desktop startup. Users must not see a WebView/Edge localhost refused-to-connect page.
- The native UI migration target is PySide6 without `QWebEngineView`, Electron, Tauri, or another browser/WebView shell.
- Keep the VBA macro portable. It must not hardcode one workstation path.

## AI Usage Rules

- Refresh Inbox should prefer the configured low-cost OpenAI model for bulk classification, then Google AI if OpenAI is unavailable, then local deterministic fallback.
- Claude/Anthropic is reserved for explicit single-email Analyze/AI Suggestion actions. Do not call Claude during bulk inbox refresh or in-app training endpoints.
- External AI should enhance layered intelligence; do not collapse the app into one giant prompt.
- AI-generated replies are suggestions only and require human review before any real guest or colleague communication.

## Training the Classifier

When Brian says **"train the model"** or **"train the classifier"**, follow `docs/TRAINING_WORKFLOW.md` exactly. The important split is:

- The running app and in-app endpoints remain zero-credit and never call Claude/OpenAI/Google during Refresh Inbox or training endpoints.
- Codex/Claude may perform an explicit agent-assisted labeling/review pass outside the running app when Brian directly asks an agent to train the model. The agent uses its model judgment on redacted/sanitized completed-request content, writes only sanitized labels/examples, retrains the local classifier, and purges raw imported bodies.

Short version:

1. **Import + label + upload + purge** in one call:
   ```python
   from outlook_dashboard.completed_training_pipeline import run_completed_pipeline
   result = run_completed_pipeline(mailbox_name="<mailbox>", batch_size=1000)
   ```
   Or via the admin API: `POST /api/training/completed-pipeline`

2. **Retrain** after examples are reviewed in Supabase:
   ```python
   from outlook_dashboard.local_classifier import train
   train()
   ```
   Or via the admin API: `POST /api/training/train`

Key constraints:
- In-app training endpoints **never call external AI** (no Claude, OpenAI, Google).
- Agent-assisted labeling is allowed only after Brian explicitly asks an agent to train the model, and it must preserve the same privacy boundary: no raw bodies, full subjects, full sender emails, message IDs, payment identifiers, or secrets in Supabase, docs, logs, or final responses.
- Raw emails are purged automatically — `source='completed_requests'` rows are deleted from SQLite after upload.
- Outlook messages are read-only: never send, delete, archive, or mutate them.
- Only `body_redacted`, `sender_domain`, and `subject_tokens` are uploaded — never raw bodies or full emails.

## Working Rules

- Prefer small, focused changes.
- Avoid broad refactors while launch, packaging, or safety work is active.
- Add or update tests for meaningful behavior changes.
- Run targeted tests for changed behavior and the full suite before packaging or major merges when practical.
- If a dependency is needed, tell Brian unless you have explicit permission to edit dependency files. In parallel-agent work, respect the file ownership list from the active user prompt.
- Use existing project patterns and helpers before introducing new abstractions.
- Use `runtime_log.get_logger()` for logging; avoid `print()` in application modules.

## Main Commands

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/ -x
python run_desktop.py
.\build_exe.ps1
```

The desktop app serves on `http://127.0.0.1:8000` by default. Runtime data and logs are local and ignored by git.
