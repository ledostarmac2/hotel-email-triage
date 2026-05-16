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

## 2026-05-16: Switch Desktop Window From Edge App Mode To pywebview / WebView2

Decision: Replace the `msedge.exe --app` subprocess with `pywebview` using the `edgechromium` (WebView2) backend.

Rationale: Edge app mode opens through the user's existing Edge browser process, causing process-handoff (immediate exit, server shutdown) and no visual separation from the browser. pywebview with WebView2 creates a truly standalone embedded window — own taskbar entry, own process, no address bar, no tabs, no browser chrome. This is the same model VS Code uses (Electron/Chromium embedded). WebView2 Runtime is pre-installed on Windows 10 21H1+ and all Windows 11 machines.

## 2026-05-16: Outlook Launch — COM-First, Start-Process Fallback

Decision: Before starting a new Outlook instance for the macro trigger, perform a thorough process search (`Get-Process OUTLOOK`). If Outlook is running, connect via COM (`GetActiveObject("Outlook.Application")`) and call `.Run(macroName)` on the existing instance. Only start a new Outlook process if none is found.

Rationale: The previous approach always called `Start-Process outlook.exe /autorun MacroName`, which on most systems opens a duplicate Outlook window rather than reusing the already-open one. The COM approach triggers the macro in-place with no UI disruption.

## 2026-05-16: Add Semantic Kernel Orchestration Layer As Additive Package

Decision: Implement the SK orchestration layer under `replyright_kernel/`, separate from `outlook_dashboard/`. The existing FastAPI dashboard is not modified.

Rationale: Keeps the proven dashboard stable while building the next-generation orchestration foundation alongside it. Future integration work (wiring SK into the `/api/emails/{id}/analyze` path) can be done incrementally and reviewed before replacing the current OpenAI call.

## 2026-05-16: Local-First Plugin Architecture For Token/Cost Control

Decision: PriorityTriage, ExecutiveSummary, and AuditCompliance run locally (no LLM) on every email. Only the draft generation step sends a request to the LLM, and it receives only the cleaned, token-optimised payload plus local metadata.

Rationale: Consistent with the existing rule of "local rules for bulk refresh, OpenAI only on demand." This pattern extends naturally to the SK layer and keeps per-email LLM cost near zero for triage operations.

## 2026-05-16: Plugin Registry Extension Points Documented In Code

Decision: `registry.py` contains clearly labelled commented extension blocks for future Microsoft Graph Outlook plugins (Tier 2) and CRM lookup plugins (Tier 3).

Rationale: Future agents and engineers need to know exactly where to insert new plugins without reading the entire codebase. Comments in the registry serve as the canonical integration guide for the orchestration layer.

## 2026-05-16: Do Not Commit Runtime Artifacts

Decision: Ignore local data, exports, logs, build output, virtual environments, and vendored dependencies.

Rationale: These files are large, machine-specific, privacy-sensitive, or reproducible. Source, docs, config examples, assets, and build scripts should be committed.
