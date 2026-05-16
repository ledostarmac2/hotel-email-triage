# Current State

Last updated: 2026-05-16

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked inbox queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and the `ExportNYCWAReservationsInboxOnly` VBA macro.
- Bulk imports use local rules for speed. OpenAI is only called when a user requests an AI response for a selected email.
- Microsoft Graph OAuth code exists but is not the active path because the user hit enterprise access restrictions in Microsoft Entra.
- `build_exe.ps1` builds `dist\ReplyRight.exe` and attempts Desktop/Start Menu shortcuts. The latest source uses Edge app mode for the desktop window.
- `python -m unittest tests.test_ai_and_database` passes with the project-local temp workaround.

## Known Local Build/Launch Notes

- Previous pywebview attempts were unstable on this workstation, so the desktop launcher now starts FastAPI and opens Edge with `--app=http://127.0.0.1:8000`.
- Startup logging is in `run_desktop.py`; packaged builds write to `dist\data\replyright-startup.log`.
- A rebuild is needed after the latest source edits before distributing the EXE again.
- Start Menu shortcut creation may fail on this locked-down Windows environment. Desktop shortcut creation succeeded earlier under the OneDrive Desktop path.
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

## Recommended Next Steps

1. Rebuild with `.\build_exe.ps1`.
2. Launch `dist\ReplyRight.exe` from the Desktop shortcut and verify the app window stays open.
3. If launch fails, inspect `dist\data\replyright-startup.log`.
4. Paste/update the latest macro from `outlook_dashboard/static/outlook_refresh_macro.bas` into Outlook VBA.
5. Test `Refresh Inbox` against `NYCWA_Reservations > Inbox`.
6. Add an `OPENAI_API_KEY` only when ready to test the AI response button.
