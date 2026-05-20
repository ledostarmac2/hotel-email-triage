# ReplyRight

ReplyRight is a local-first desktop AI email triage assistant for the Waldorf Astoria New York reservations workflow.

It reads the hotel shared inbox, stores imported messages in local SQLite, ranks operational urgency, assigns department ownership, summarizes required action, flags risk, supports human correction, and prepares AI-assisted reply suggestions for review.

ReplyRight does **not** send, delete, archive, move, categorize, mark read, or otherwise mutate Outlook messages.

## Active App

The runnable app is:

```text
outlook_dashboard/
run_desktop.py
```

The desktop build is a PyInstaller-packaged FastAPI server with a native PySide6 shell. The backend health check runs on:

```text
http://127.0.0.1:8000
```

The `app/` directory is an inactive Next.js scaffold. Do not treat it as the active application unless a future migration is explicitly requested.

## What It Does

- Imports `NYCWA_Reservations > Inbox` from classic Outlook for Windows through read-only `pywin32` COM.
- Keeps Microsoft Graph OAuth as an optional read-only path when Entra credentials and mailbox access exist.
- Stores local operational data in SQLite under `data/`.
- Uses Supabase Auth for login/session validation and Supabase tables for shared feedback, approved rules, known senders, prompt versions, and training examples.
- Runs deterministic triage and local classifier prediction where available.
- Uses OpenAI for bulk Refresh Inbox classification when configured, Google AI as refresh fallback, and local deterministic triage when external AI is unavailable.
- Uses Claude only for explicit single-email Analyze/AI Suggestion actions.
- Redacts payment-like and sensitive identifiers before external AI calls or training export.
- Provides admin tools for training pipeline runs, human review of training examples, local classifier training, prompt management, users, rules, and diagnostics.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional local secrets can be placed in `.env`. Do not commit `.env`.

```powershell
Copy-Item .env.example .env
```

Common local settings:

```env
APP_HOST=127.0.0.1
APP_PORT=8000
OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations
OUTLOOK_EXPORT_FOLDER=Inbox
OPENAI_API_KEY=
GOOGLE_AI_API_KEY=
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
REPLYRIGHT_ADMIN_EMAIL=
REPLYRIGHT_ADMIN_PASSWORD=
```

Some credentials are also injected from `outlook_dashboard/bundled_secrets.py` after `.env` is loaded. `.env` takes precedence.

## Run

```powershell
python run_desktop.py
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The app does not seed mock/demo messages in the active dashboard path. Refresh Inbox treats Outlook as the source of truth and removes local rows that are no longer in the current Outlook import.

## Build The Windows EXE

```powershell
.\build_exe.ps1
.\installer\build_installer.ps1
```

Output:

```text
dist\ReplyRight\ReplyRight.exe
```

The EXE starts the local FastAPI server, waits for `/healthz`, then opens the native PySide6 desktop shell. Runtime data, copied secrets, logs, and packaged binaries are ignored by git.

User-facing releases should distribute `installer\output\ReplyRightSetup-v{version}.exe`. The installer is per-user/no-admin and installs under `%LOCALAPPDATA%\Programs\ReplyRight`.

## Training Pipeline

The admin training pipeline exports completed local emails into Supabase `training_examples`.

Default mode is zero-credit:

```text
completed local email
  -> latest-message cleanup
  -> redaction
  -> existing analysis labels
  -> service-role upload to training_examples
  -> training_pipeline_log entry in SQLite
```

`refine=true` is retained for backwards compatibility but does not call Claude/Anthropic.

The local classifier trains from human-reviewed Supabase examples and stores model artifacts in local SQLite.

See:

- `docs/TRAINING_PIPELINE.md`
- `docs/CLASSIFIER.md`

## Testing

Tests require no live credentials. External services are mocked or disabled.

Run the full suite:

```powershell
python -m pytest tests/ -x
```

Run targeted suites:

```powershell
python -m pytest tests/test_hotel_entities.py tests/test_travel_programs.py tests/test_urgency_engine.py -v
python -m pytest tests/test_training_pipeline.py tests/test_ai_and_database.py -v
```

See `docs/TESTING.md` for the full guide.

## Key Docs

- `AGENTS.md` - instructions for future agents.
- `docs/CURRENT_STATE.md` - latest project truth.
- `docs/ARCHITECTURE.md` - current runtime architecture.
- `docs/PROJECT_STRUCTURE.md` - repository layout and cleanup policy.
- `docs/ROADMAP.md` - product and architecture roadmap.
- `docs/SECURITY_AND_PRIVACY.md` - safety and privacy rules.
- `docs/DEPLOYMENT.md` - packaging and release workflow.
- `docs/OPERATIONS_GUIDE.md` - hotel-operator workflow guide.

## Notes Before Live Use

- Keep Outlook behavior read-only.
- Review AI drafts before using them with guests or colleagues.
- Do not store or commit mailbox data, raw email bodies, `.env`, Supabase keys, cookies, or packaged runtime data.
- Do not add reply sending without a separate approval, audit, and permission design.
