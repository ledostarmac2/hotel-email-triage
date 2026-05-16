# ReplyRight Architecture

ReplyRight is a local, read-only Outlook inbox triage dashboard for hotel reservations work. It ranks emails by urgency, summarizes threads, lists internal next steps, and generates an AI response draft only when the user asks for one.

## Active Application

The current runnable app is the Python/FastAPI dashboard in `outlook_dashboard/`, launched by `run_desktop.py` or packaged with `build_exe.ps1`.

```text
run_desktop.py
  starts FastAPI on 127.0.0.1:8000
  opens a pywebview/WebView2 desktop window

outlook_dashboard/
  main.py              FastAPI routes and app lifecycle
  config.py            env loading and runtime paths
  database.py          SQLite schema and persistence helpers
  graph.py             optional Microsoft Graph OAuth/read sync
  outlook_desktop.py   read-only Outlook desktop import plus macro fallback
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
3. FastAPI reads classic Outlook directly through read-only `pywin32` COM automation.
4. The importer reads only `NYCWA_Reservations > Inbox`, saves local `.msg` copies under the app data export folder, and returns a normalized message payload in-process.
5. FastAPI upserts messages into local SQLite.
6. After a successful Outlook refresh, any local email row whose message id was not in the current Outlook import is deleted. This removes mock/demo/stale rows and makes Outlook refresh the source of truth.
7. `triage_email()` applies fast local rules for summary, category, contact type, owner, missing info, risk flags, and urgency.
8. The dashboard fetches `/api/emails`, groups rows by `conversation_id`, and computes conversation-level triage from the latest few messages.
9. Conversation-level sentiment ignores quoted Outlook history where possible, and stored local feedback can override or guide urgency, owner, category, contact type, and sentiment.
10. Urgency remains arrival-aware but is conservative: same/next-day blockers and serious risk can reach level 5, while completed/thank-you/form-submission updates are lowered unless a high-risk signal is present.
11. The dashboard sorts conversation groups by urgency score 1-5 and renders the queue.
12. If `pywin32` is unavailable, ReplyRight can still fall back to starting classic Outlook with `/autorun ExportNYCWAReservationsInboxOnly` for the legacy VBA macro path.
13. When the user clicks `AI Response`, `/api/emails/{id}/analyze` calls OpenAI if configured; otherwise it falls back to a deterministic local draft.

## Adaptive Feedback

Each conversation detail view includes a local feedback box. The user can explain why the app should relabel a thread and optionally choose corrected urgency or owner.

`POST /api/emails/{email_id}/feedback` stores the correction locally and immediately recomputes the selected conversation. Feedback is local-only today and is designed as the first step toward the Supabase shared-learning roadmap in `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md`.

## Persistence

SQLite is local by default:

```text
data/hotel_email_triage.sqlite3
```

Tables:

- `emails`
- `email_analysis`
- `triage_feedback`
- `oauth_tokens`
- `oauth_states`
- `sync_runs`

The `data/` directory is intentionally ignored because it can contain mailbox content, local tokens, exports, and logs.

## Integrations

Outlook desktop is the primary current integration because ChatGPT/Outlook connector access and Entra app registration were blocked by enterprise restrictions.

Microsoft Graph OAuth remains implemented as an optional read-only path. It requires Entra app registration values in `.env` and shared mailbox permission.

OpenAI is optional. Bulk refresh uses local rules for performance and cost control. OpenAI is used only for explicit per-email analysis/draft requests when `OPENAI_API_KEY` is configured.

## Build Shape

`build_exe.ps1` packages `run_desktop.py` with PyInstaller, embeds the ReplyRight icon, and attempts to create Desktop and Start Menu shortcuts. The app window is a pywebview/WebView2 desktop window.

Ignored build/runtime folders include `.vendor/`, `.build-tmp/`, `build/`, `dist/`, `data/`, `.venv/`, and local temp folders.
