# Deployment

Last updated: 2026-05-20

## Active Deployment Shape

ReplyRight deploys as an installer-first Windows desktop application.

Primary user-facing release asset:

```text
ReplyRightSetup-v{version}.exe
```

Installed executable:

```text
ReplyRight.exe
```

Runtime shape:

```text
ReplyRight.exe
  -> run_desktop.py
  -> FastAPI backend on 127.0.0.1
  -> health-gated startup through /healthz
  -> native PySide6 desktop shell
  -> local SQLite data under the install data folder
```

The desktop shell must not use `QWebEngineView`, Electron, Tauri, pywebview, or another browser/WebView wrapper.

## Fresh Windows Install

The installer bundles the Python runtime application and PyInstaller-collected dependencies. A normal user should not need to install Python, pip, Node, or project dependencies.

Fresh machine requirements:

- Windows 10/11.
- Classic Outlook for live Outlook COM inbox refresh.
- Access to the configured shared mailbox, usually `NYCWA_Reservations`.
- Network access for optional Supabase, SMTP invite/reset emails, AI providers, and GitHub update checks.

Outlook remains read-only. ReplyRight reads/imports messages and writes local SQLite state; it does not send, move, delete, mark read, or categorize Outlook messages.

## Installer Contract

The Inno Setup installer is per-user by default and should avoid admin rights.

Current contract:

- `PrivilegesRequired=lowest`.
- Default install directory: `%LOCALAPPDATA%\Programs\ReplyRight`.
- Desktop shortcut is created under the current user's desktop only.
- Runtime data, SQLite databases, logs, and local `.env` files are excluded from the installer payload.

Do not change this to a Program Files/admin install unless there is a deliberate enterprise deployment decision.

## User Onboarding

Supabase Auth is the shared identity source when configured.

Supported today:

- First admin seeding/repair from deployment config.
- Admin user listing.
- Admin-created invite.
- Password reset by token.
- Manual invite-link fallback when SMTP is not configured or send fails.

Important limitation:

- Invite/reset links are local app links (`http://127.0.0.1:<port>/reset-password?...`). They work best on the machine where the local ReplyRight backend is running. For broad multi-machine rollout, add a public redirect service, Supabase-hosted invite flow, or a temporary-password/on-first-login reset flow.

SMTP:

- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` for invite/reset emails.
- If SMTP is unavailable, admins can copy the returned `invite_url` from `/api/auth/invite`.

## Email Source

ReplyRight does not receive email itself.

Current source of truth:

```text
Classic Outlook profile
  -> shared mailbox/folder
  -> read-only COM import
  -> local SQLite
  -> analysis and queue UI
```

Default config:

```text
OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations
OUTLOOK_EXPORT_FOLDER=Inbox
```

Microsoft Graph code exists but is not the active path because tenant/enterprise access can block it. A future centralized mailbox worker would require a separate approved Graph app registration or another server-side mail ingestion design.

## Local Build

From the repository root:

```powershell
.\build_exe.ps1
.\installer\build_installer.ps1
```

`build_exe.ps1` builds the internal PyInstaller onedir app at:

```text
dist\ReplyRight\ReplyRight.exe
```

`installer\build_installer.ps1` builds:

```text
installer\output\ReplyRightSetup-v{version}.exe
```

The setup installer is the artifact users should download. The onedir EXE is an internal build input.

## Smoke Tests

Packaged health smoke:

```powershell
dist\ReplyRight\ReplyRight.exe --health-smoke
```

Source tests:

```powershell
python -m pytest tests/test_desktop_startup.py tests/test_installer_contract.py tests/test_api_workflow_pytest.py -q --timeout=60
```

Manual clean-machine smoke:

1. Install `ReplyRightSetup-v{version}.exe` as a normal user.
2. Confirm no UAC prompt appears.
3. Launch from Start Menu or desktop shortcut.
4. Confirm the PySide6 login window opens only after backend health succeeds.
5. Sign in with the seeded/admin account.
6. Open Admin diagnostics and verify Supabase, SMTP, Outlook, classifier, and version status.
7. Click Refresh Inbox with classic Outlook open and the shared mailbox available.
8. Confirm imported messages render and no Outlook messages are mutated.

## Diagnostics

Admins can call:

```text
GET /api/admin/deployment/diagnostics
```

The response intentionally contains no secrets. It reports:

- app version/commit/build date
- Python/runtime/frozen state
- database path/existence
- Supabase/SMTP/Graph/provider configured booleans
- Outlook COM/platform status
- mailbox/folder names
- local classifier version/targets
- runtime warnings

## GitHub Release Path

GitHub Actions includes Windows lint/test/build, installer build, Docker health, and tag-based release jobs.

The Docker path is a CI/server smoke target, not the Windows desktop shell. It builds from the root `Dockerfile`, runs `outlook_dashboard.main:app` with Uvicorn on port 8000, and health-checks `/api/health`. Keep `Dockerfile` present while `.github/workflows/build.yml` includes the `docker-build` job.

Release assets must be installer-first:

```text
ReplyRightSetup-v{version}.exe
```

Raw `dist\ReplyRight\ReplyRight.exe` must not be attached as the default user download.

Before tagging:

- Run targeted tests.
- Build locally.
- Build the installer locally.
- Run `dist\ReplyRight\ReplyRight.exe --health-smoke`.
- Confirm installer output exists.
- Confirm docs and handoff are current.
- Confirm ignored runtime files are not staged.

## Troubleshooting

If the EXE fails to launch:

1. Check `data\replyright-startup.log` under the installed app folder.
2. Run `ReplyRight.exe --health-smoke`.
3. Confirm bundled dependencies were collected.
4. Rebuild with a clean `.vendor` if packaging looks stale.

If Outlook refresh fails:

1. Confirm classic Outlook is installed and open.
2. Confirm the shared mailbox/folder exists.
3. Confirm the signed-in Windows/Outlook user has access.
4. Confirm bundled `pywin32` is present.
5. Use the VBA macro fallback only when direct COM import is unavailable.

If invites do not email:

1. Check Admin diagnostics for `smtp_configured`.
2. Confirm SMTP credentials outside ReplyRight.
3. Use the manual `invite_url` fallback for a beta test.
4. For multi-machine production rollout, implement a public/Supabase-hosted invite redirect flow.

## Do Not Commit or Bundle

- `.env`
- `dist\ReplyRight\.env`
- local SQLite databases
- runtime data
- startup logs
- `.msg` exports
- packaged EXE or installer binaries
- service-role keys
- provider API keys
