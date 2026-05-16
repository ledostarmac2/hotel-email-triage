# ReplyRight Architecture

ReplyRight is a local, read-only Outlook inbox triage dashboard for hotel reservations work. It ranks emails by urgency, summarizes threads, lists internal next steps, and generates an AI response draft only when the user asks for one.

## Active Application

The current runnable app is the Python/FastAPI dashboard in `outlook_dashboard/`, launched by `run_desktop.py` or packaged with `build_exe.ps1`.

```text
run_desktop.py
  starts FastAPI on 127.0.0.1:8000
  opens Microsoft Edge in app-window mode

outlook_dashboard/
  main.py              FastAPI routes and app lifecycle
  config.py            env loading and runtime paths
  database.py          SQLite schema and persistence helpers
  graph.py             optional Microsoft Graph OAuth/read sync
  outlook_desktop.py   starts the Outlook VBA macro
  ai.py                local triage and on-demand OpenAI draft generation
  redaction.py         payment-like sensitive text redaction
  taxonomy.py          categories, priorities, risks, statuses, owners
  static/              HTML/CSS/JS dashboard, branding, VBA macro

tests/
  test_ai_and_database.py
```

The `app/` directory is a Next.js/Prisma scaffold from an earlier production direction. It is not the current executable path, but keep it intact unless a migration is requested.

The `reference/` directory contains tracked reference project snapshots used for inspiration. It is not active runtime code.

## Data Flow

1. User clicks `Refresh Inbox`.
2. FastAPI calls `outlook_desktop.export_mailbox_folder_to_msg()`.
3. That launches classic Outlook with `/autorun ExportNYCWAReservationsInboxOnly`.
4. The VBA macro reads only `NYCWA_Reservations > Inbox`, saves `.msg` copies under the user's Documents folder, builds a JSON payload, and posts it to `/api/outlook-desktop/import-json`.
5. FastAPI upserts messages into local SQLite.
6. `triage_email()` applies fast local rules for summary, category, owner, missing info, risk flags, and urgency.
7. The dashboard fetches `/api/emails`, sorts by urgency score 1-5, and renders the queue.
8. When the user clicks `AI Response`, `/api/emails/{id}/analyze` calls OpenAI if configured; otherwise it falls back to a deterministic local draft.

## Persistence

SQLite is local by default:

```text
data/hotel_email_triage.sqlite3
```

Tables:

- `emails`
- `email_analysis`
- `oauth_tokens`
- `oauth_states`
- `sync_runs`

The `data/` directory is intentionally ignored because it can contain mailbox content, local tokens, exports, and logs.

## Integrations

Outlook desktop is the primary current integration because ChatGPT/Outlook connector access and Entra app registration were blocked by enterprise restrictions.

Microsoft Graph OAuth remains implemented as an optional read-only path. It requires Entra app registration values in `.env` and shared mailbox permission.

OpenAI is optional. Bulk refresh uses local rules for performance and cost control. OpenAI is used only for explicit per-email analysis/draft requests when `OPENAI_API_KEY` is configured.

## Build Shape

`build_exe.ps1` packages `run_desktop.py` with PyInstaller, embeds the ReplyRight icon, and attempts to create Desktop and Start Menu shortcuts. The app window is an Edge app-mode window, not pywebview.

Ignored build/runtime folders include `.vendor/`, `.build-tmp/`, `build/`, `dist/`, `data/`, `.venv/`, and local temp folders.
