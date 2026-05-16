# Decisions

## 2026-05-16: Current Runtime Is Python/FastAPI

Decision: Treat `outlook_dashboard/` and `run_desktop.py` as the active product path.

Rationale: It is the working dashboard and EXE path. The `app/` Next.js scaffold remains available for a future migration but is not the current app.

## 2026-05-16: Outlook Stays Read-Only

Decision: ReplyRight may read/import Outlook mail and update local review status only.

Rationale: Hotel reservations email is operationally sensitive. Sending, moving, deleting, marking read, or categorizing Outlook messages needs separate user approval and a safer workflow.

## 2026-05-16: Use VBA Macro As Primary Outlook Ingestion

Decision: Use classic Outlook VBA to export/import `NYCWA_Reservations > Inbox`.

Rationale: The ChatGPT Outlook connector was blocked by enterprise policy, and Entra app registration access was unavailable. The macro path works with the user's existing desktop Outlook access.

## 2026-05-16: Local Rules For Bulk Triage, OpenAI On Demand

Decision: Bulk refresh uses deterministic local triage. OpenAI is reserved for explicit per-email response generation.

Rationale: This keeps refresh fast, cheaper, and more reliable while still allowing higher-quality response drafting when requested.

## 2026-05-16: SQLite Local Storage

Decision: Use local SQLite for messages, analysis, OAuth tokens, sync logs, and local statuses.

Rationale: It keeps the desktop app lightweight and avoids introducing a server database before the workflow is stable.

## 2026-05-16: Edge App Window Instead Of pywebview

Decision: The EXE starts FastAPI and opens Microsoft Edge in app mode.

Rationale: pywebview was unstable in the current Windows environment. Edge app mode gives a standalone-window feel with less native packaging risk.

## 2026-05-16: Do Not Commit Runtime Artifacts

Decision: Ignore local data, exports, logs, build output, virtual environments, and vendored dependencies.

Rationale: These files are large, machine-specific, privacy-sensitive, or reproducible. Source, docs, config examples, assets, and build scripts should be committed.
