# Current State

Last updated: 2026-05-16 (desktop launcher, UI polish, Outlook COM fix, build hardening)

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked inbox queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and the `ExportNYCWAReservationsInboxOnly` VBA macro.
- Bulk imports use local rules for speed. OpenAI is only called when a user requests an AI response for a selected email.
- Microsoft Graph OAuth code exists but is not the active path because the user hit enterprise access restrictions in Microsoft Entra.
- `build_exe.ps1` builds `dist\ReplyRight.exe` and attempts Desktop/Start Menu shortcuts. The latest source uses **pywebview** (WebView2/edgechromium backend) for the desktop window.
- A fresh `dist\ReplyRight.exe` was built 2026-05-16 and shortcuts were updated. It has not yet been launch-tested by the user.
- `python -m unittest tests.test_ai_and_database` passes with the project-local temp workaround.

## Known Local Build/Launch Notes

- Desktop launcher uses **pywebview** (`webview.start(gui="edgechromium")`). WebView2 runtime ships with Windows 10/11 (22H2+) but must be present on any machine running the EXE.
- `run_desktop.py` does a pre-flight `import clr` check and raises a descriptive error if pythonnet is missing, rather than crashing natively with no log entry.
- Startup logging is in `run_desktop.py`; packaged builds write to `dist\data\replyright-startup.log`.
- `build_exe.ps1` auto-skips `.venv` and `.build-venv` to find system Python (VS Code auto-activates project venvs). If `.vendor` exists but is empty/partial, delete it and rebuild — the existence check short-circuits pip install.
- If Defender locks `dist\ReplyRight.exe` during a rebuild, the script falls back to renaming the old EXE to `.exe.old`. If both are locked, delete them manually first.
- Start Menu shortcut creation may fail on this locked-down Windows environment. Desktop shortcut creation uses the OneDrive Desktop path as a fallback.
- Local Python temp-directory permissions were unreliable. `build_support/sitecustomize.py` exists as a workaround for project-local dependency installation.

## Config Requirements

Copy `.env.example` to `.env` for local runs. `.env` must not be committed.

Important variables:

- `OPENAI_API_KEY` for on-demand AI responses.
- `OPENAI_MODEL`, default `gpt-4.1-mini`.
- `APP_HOST=127.0.0.1`
- `APP_PORT=8000`
- `OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations`
- `OUTLOOK_EXPORT_FOLDER=Inbox`
- Optional Microsoft Graph values: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`, `MICROSOFT_REDIRECT_URI`, `SHARED_MAILBOX_EMAIL`.

## Current Risks

- The VBA macro must be installed manually in Outlook and must match the configured macro name.
- The macro posts to `http://127.0.0.1:8000`; the app must be running before refresh.
- The desktop launcher still needs final user-side validation after the most recent source edits.
- AI drafts are suggestions only and require human review.
- This app intentionally does not mutate Outlook messages; adding send/archive/move/category actions requires a new design and approval.
- Local mailbox exports and SQLite data are ignored for privacy and are not portable through git.

## Semantic Kernel Orchestration Layer

A new `replyright_kernel/` Python package implements the foundational SK orchestration layer:

- **PriorityTriagePlugin** — local urgency scoring 1–5 (regex/keyword, no LLM cost)
- **ExecutiveSummaryPlugin** — strips HTML, quoted threads, signatures, legal footers, tracking noise; enforces 8 000-char token budget
- **AuditCompliancePlugin** — pre-display compliance scan; blocks guarantees, fault admissions, payment leakage, legal/medical/discrimination risk language, unapproved promises
- **engine.py / registry.py** — builds and registers the kernel; clearly labelled extension points for future Graph and CRM plugins
- **demo.py** — runnable four-step pipeline demo (`python -m replyright_kernel.demo`)

The layer is additive. It does not touch the existing FastAPI dashboard, Next.js scaffold, or Outlook read path.

Tests: `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` (59 tests, no API key required).

`OPENAI_MODEL` defaults to `gpt-5.5` in the kernel layer; the dashboard still uses `gpt-4.1-mini` unless overridden. `KERNEL_LOG_LEVEL` controls kernel log verbosity.

## Recommended Next Steps

1. **Launch `dist\ReplyRight.exe`** from the Desktop shortcut (just rebuilt). If the pywebview window opens and the dashboard loads, the core launcher is working.
2. **If launch fails**: inspect `dist\data\replyright-startup.log`. Look for `pythonnet (clr) is not available` — if seen, delete `.vendor` and re-run `.\build_exe.ps1` so pip re-installs pythonnet.
3. **Test Refresh Inbox**: with Outlook open and the VBA macro installed, click Refresh Inbox. The app runs `cscript.exe` with a VBScript file that calls `ol.Run "MacroName"` via IDispatch. If it fails with a VBScript error, check Outlook's Trust Center → Macro Settings → Enable all macros.
4. **Paste/update the macro**: import `outlook_dashboard/static/outlook_refresh_macro.bas` into Outlook VBA (Alt+F11). Macro must be named `ExportNYCWAReservationsInboxOnly` or match `OUTLOOK_EXPORT_MACRO` in `.env`.
5. **Wire `replyright_kernel`** into `outlook_dashboard/ai.py` when ready to replace/supplement the on-demand OpenAI call.
6. **Add `OPENAI_API_KEY`** only when ready to test the AI response button.
