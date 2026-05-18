# Release Blockers: v0.1.0

Last updated: 2026-05-18

## Observed Issue

The GitHub release v0.1.0 is not acceptable as a user release.

Observed behavior after downloading and running the release asset:

- A ReplyRight desktop window opened.
- The window displayed a WebView/Edge localhost error.
- Error text included `127.0.0.1 refused to connect` and `ERR_CONNECTION_REFUSED`.
- The release appeared to expose a bare `ReplyRight.exe` as the user-facing download instead of a setup installer.

## Why This Blocks Release

ReplyRight must feel like a standalone Windows desktop application. A user should never see a browser-style localhost failure page. That error exposes the implementation detail that the app is a FastAPI server plus WebView shell, and it makes the release look broken even if the backend might recover later.

The release asset strategy is also wrong for broader use. A bare EXE download does not provide an install path, Start Menu shortcut, uninstall entry, WebView2 handling, or normal Windows setup experience.

## Root Causes Found

- `run_desktop.py` opened pywebview after a health wait, but the wait targeted `/api/health` and had a shorter timeout than the v0.1.1 requirement.
- The launcher still had browser fallback behavior for missing pywebview, missing WebView2, missing pythonnet, or WebView startup failure.
- The fallback could open a system browser or leave a browser-like localhost failure visible.
- The GitHub release workflow was historically oriented around raw EXE publishing. It now needs to be installer-first.
- The updater was written around EXE replacement and needed to prefer setup installer assets.

## Immediate v0.1.1 Fix Requirements

v0.1.1 must:

1. Start the backend before any desktop window is opened.
2. Poll a public lightweight health endpoint: `GET /healthz`.
3. Open pywebview only after `/healthz` returns successfully.
4. Use a bounded startup timeout of about 30 seconds.
5. Avoid opening an external browser as fallback.
6. Show a controlled ReplyRight startup error dialog if startup fails.
7. Include the safe startup log path in the error dialog.
8. Use an available localhost port when the preferred port is occupied, or fail gracefully with a controlled error.
9. Publish a setup installer as the primary release asset.
10. Keep Outlook read-only and preserve all human review gates.

## Code Changes Applied For v0.1.1

- Added `GET /healthz`.
- Added startup health polling against `/healthz`.
- Increased startup wait to 30 seconds.
- Removed browser fallback from the desktop launcher.
- Added controlled startup error messaging with the startup log path.
- Changed launcher port selection to prefer configured `APP_PORT`, then choose an available dynamic port only when needed.
- Updated updater asset selection to prefer `ReplyRightSetup-*.exe`.
- Changed updater installation flow to run the installer instead of replacing the EXE directly.
- Bumped source version to `0.1.1`.

## Release Acceptance Criteria

Before tagging v0.1.1:

- `python -m pytest tests/test_desktop_startup.py -q` passes.
- `python -m pytest tests/ -x --timeout=30` passes locally or in CI.
- `.\build_exe.ps1` succeeds.
- `.\installer\build_installer.ps1` succeeds.
- The release workflow uploads `ReplyRightSetup-v0.1.1.exe`.
- The release does not present raw `ReplyRight.exe` as the main user download.
- Starting the installed app never shows a WebView localhost refused page.
- If startup fails, the user sees a ReplyRight-controlled error dialog with a log path.
- `dist\data\replyright-startup.log` contains safe diagnostics only.

## Do Not Change For This Repair

- Do not add reply sending.
- Do not mutate Outlook messages.
- Do not migrate to `app/`.
- Do not wire `replyright_kernel/` into production.
- Do not log raw email bodies.
- Do not weaken PII redaction.
