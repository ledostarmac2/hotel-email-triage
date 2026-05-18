# ReplyRight Architecture

ReplyRight is a local, read-only Outlook inbox triage dashboard for Waldorf Astoria New York reservations work. It ranks emails by urgency, summarizes threads, lists internal next steps, and generates an AI response draft only when the user asks for one.

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
  auth.py              local ReplyRight users, sessions, invite/reset email helpers
  graph.py             optional Microsoft Graph OAuth/read sync
  outlook_desktop.py   read-only Outlook desktop import plus macro fallback
  ai.py                triage rules, OpenAI refresh-analysis target, Claude Opus on-demand draft target
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
7. Current implementation: `triage_email()` attempts OpenAI refresh classification when `OPENAI_API_KEY` is configured, using the configured `OPENAI_MODEL` default of `gpt-5.4-nano`; if OpenAI is not configured and `GOOGLE_AI_API_KEY` is present, it attempts Google AI Studio/Gemini refresh classification with structured JSON output; local deterministic triage remains the fallback when external AI is unavailable or errors.
8. Target refinement: split refresh classification into clearer staged OpenAI steps for fact extraction, sender/contact detection, action detection, owner assignment, urgency scoring, missing-information detection, and summary/required-action generation.
9. The dashboard fetches `/api/emails`, groups rows by `conversation_id`, and computes conversation-level triage from the latest few messages.
10. Conversation-level sentiment ignores quoted Outlook history where possible, and stored local feedback can override or guide urgency, owner, category, contact type, sentiment, status, and summary/reply quality learning signals. Downloaded known-sender mappings can also override local owner/contact-type classification for matching sender domains.
11. Urgency remains arrival-aware but is conservative: same/next-day blockers and serious risk can reach level 5, while completed/thank-you/form-submission updates are lowered unless a high-risk signal is present.
12. The dashboard sorts conversation groups by urgency score 1-5 and renders the queue.
13. If `pywin32` is unavailable, ReplyRight can still fall back to starting classic Outlook with `/autorun ExportNYCWAReservationsInboxOnly` for the legacy VBA macro path.
14. When the user clicks `AI Suggestion`, the target engine is Claude Opus only. If Claude is unavailable, the UI should show a clear error/fallback state rather than silently treating refresh-classification OpenAI as the same feature.

## Adaptive Feedback

Each conversation detail view includes a local feedback box. The user can explain why the app should relabel a thread and optionally choose corrected urgency, owner, category, contact type, sentiment, status, summary quality rating, and reply quality rating.

`POST /api/emails/{email_id}/feedback` stores the correction locally, uploads a sanitized feedback event to Supabase when configured, queues failed Supabase uploads for retry, and immediately recomputes the selected conversation.

## Authentication

The dashboard is gated by local ReplyRight accounts stored in SQLite. The configured admin account comes from `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` in `.env`; startup creates or repairs that admin account without requiring database deletion.

Sessions use an HttpOnly `rr_session` cookie. Invite and password reset flows send SMTP links when SMTP settings are configured.

## Persistence

SQLite is local by default:

```text
data/hotel_email_triage.sqlite3
```

Tables:

- `emails`
- `email_analysis`
- `triage_feedback`
- `users`
- `sessions`
- `password_reset_tokens`
- `oauth_tokens`
- `oauth_states`
- `sync_runs`
- `rule_candidates`
- `supabase_rule_cache`
- `supabase_feedback_queue`
- `supabase_prompt_cache`
- `supabase_known_sender_cache`

The `data/` directory is intentionally ignored because it can contain mailbox content, local tokens, exports, and logs.

## Integrations

Outlook desktop is the primary current integration because ChatGPT/Outlook connector access and Entra app registration were blocked by enterprise restrictions.

Microsoft Graph OAuth remains implemented as an optional read-only path. It requires Entra app registration values in `.env` and shared mailbox permission.

OpenAI is the preferred refresh-classification engine when configured. On Refresh Inbox, ReplyRight assigns urgency, owner, category, contact type, sentiment, missing information, summary, and required actions with OpenAI, using the configured `OPENAI_MODEL` default of `gpt-5.4-nano` after checking official OpenAI docs on 2026-05-17.

Google AI Studio/Gemini is supported as an optional refresh-classification fallback through `GOOGLE_AI_API_KEY` and `GOOGLE_AI_MODEL` when OpenAI is not configured. Google output uses the Gemini REST `responseMimeType` and `responseJsonSchema` structured-output fields. No Google key is stored in tracked files; use the ignored `.env` file or local machine environment.

Local rules remain the fallback when external AI is unavailable or errors.

Claude Opus is the target on-demand `AI Suggestion` engine for drafting/refining the guest-facing response. Do not use Claude for bulk refresh.

Supabase startup sync downloads approved classification rules, active prompt versions, and known sender mappings when configured. These are cached in local SQLite so the app can keep using the last-known shared configuration if Supabase is temporarily unreachable. Known sender mappings are applied to routine triage by sender domain for owner/contact-type corrections.

ReplyRight is single-property for Waldorf Astoria New York / `NYCWA_Reservations`. Multi-property and cross-property support are intentionally out of scope unless Brian explicitly reopens that direction.

## Long-Term Local Intelligence

The Phase 7 roadmap adds a privacy-preserving, hotel-specific local learning layer. The target is not to train a full LLM from scratch. The target is a hybrid system that uses rules, Supabase feedback, sanitized historical examples, embeddings, lightweight local classifiers, and external AI fallback.

The long-term runtime goal is:

```text
New email
  -> redact/sanitize sensitive data for training or external AI use
  -> apply deterministic hotel rules
  -> run local classifiers for urgency, owner, category, status, missing info, reply required, escalation required
  -> use local prediction when confidence is high
  -> mark review suggested when confidence is medium
  -> call OpenAI/Claude only for low-confidence, complex, sensitive, summary, or reply-drafting work
  -> save user corrections back into Supabase for future retraining
```

Phase 7 training data must be sanitized by default. Raw guest emails, reservation numbers, payment details, attachments, and other PII should not be stored in Supabase training tables unless an explicit developer/admin override is added later.

The preferred first local model approach is sentence-transformer embeddings plus independent lightweight classifiers such as Logistic Regression or Linear SVM for structured labels. Model versions, metrics, prediction logs, and human review queues should be tracked in Supabase, with local artifacts versioned and rollbacks available.

## Build Shape

`build_exe.ps1` packages `run_desktop.py` with PyInstaller, embeds the ReplyRight icon, and attempts to create Desktop and Start Menu shortcuts. The app window is a pywebview/WebView2 desktop window.

Ignored build/runtime folders include `.vendor/`, `.build-tmp/`, `build/`, `dist/`, `data/`, `.venv/`, and local temp folders.
