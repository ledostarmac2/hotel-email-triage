# Deployment

Last updated: 2026-05-18

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

The EXE contains:

- `run_desktop.py`
- FastAPI app in `outlook_dashboard/`
- static dashboard assets
- pywebview desktop shell
- bundled Python dependencies collected by PyInstaller

Runtime data is written next to the executable under `dist\data\` for packaged builds.

## Local Build

From the repository root:

```powershell
.\build_exe.ps1
.\installer\build_installer.ps1
```

`build_exe.ps1` builds the internal PyInstaller executable at `dist\ReplyRight.exe`.

`installer\build_installer.ps1` builds the Inno Setup installer at `installer\output\ReplyRightSetup-v{version}.exe`.

The setup installer is the artifact users should download. The raw EXE is an internal build input.

Important dynamic dependency collection includes:

- `outlook_dashboard`
- `anthropic`
- `pythonnet`
- `pywin32` / COM support
- `sklearn`
- `scikit_learn`
- `dateparser`
- `joblib`
- `threadpoolctl`

Keep the sklearn/dateparser/joblib/threadpoolctl flags in the same PyInstaller collection block.

## Runtime Requirements

- Windows 10/11
- WebView2 runtime
- Classic Outlook for direct COM import
- `pywin32` bundled for direct Outlook import
- Network access for optional Supabase, OpenAI, Google AI, Claude, GitHub releases, and Microsoft Graph

If Outlook COM is unavailable, the legacy VBA macro path remains a fallback.

## Local Run

```powershell
python run_desktop.py
```

Default URL:

```text
http://127.0.0.1:8000
```

## Smoke Test The EXE

Start the EXE in the background or off-screen:

```powershell
Start-Process "dist\ReplyRight.exe"
Start-Sleep -Seconds 8
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

Expected:

```text
ok = true
```

The desktop launcher also checks `/healthz` before opening pywebview. If startup fails, it should show a controlled ReplyRight error dialog with the startup log path. It must not open an external browser fallback or show a localhost refused-to-connect page.

Stop the process after testing if it is not needed:

```powershell
Get-Process ReplyRight -ErrorAction SilentlyContinue | Stop-Process
```

## Training Pipeline Packaging Check

Confirm the packaged SQLite database has the training log table:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'dist\data\hotel_email_triage.sqlite3'); print(c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='training_pipeline_log'\").fetchall())"
```

Trigger a training run through the API only after authenticated admin login. Do not print passwords, cookies, or service-role keys.

## GitHub Release Path

GitHub Actions includes Windows lint/test/build, installer build, Docker health, and tag-based release jobs.

Release assets must be installer-first:

```text
ReplyRightSetup-v{version}.exe
```

Raw `dist\ReplyRight.exe` must not be attached as the default user download.

Typical release flow:

```powershell
git tag v0.1.1
git push origin v0.1.1
```

Before tagging:

- Run tests.
- Build locally.
- Build the installer locally.
- Smoke-test packaged `/healthz`.
- Confirm installer output exists.
- Confirm `docs/CURRENT_STATE.md` and `docs/HANDOFF.md` are current.
- Confirm ignored runtime files are not staged.

## Installer

The Inno Setup installer files live under:

```text
installer/replyright_setup.iss
installer/build_installer.ps1
```

Use them after the EXE build is known good. See `docs/INSTALLER_STRATEGY.md`.

## Auto-Updater

`outlook_dashboard/updater.py` checks GitHub releases for updates. Update diagnostics and release notes should be improved before broader rollout.

## Troubleshooting

If the EXE fails to launch:

1. Check `dist\data\replyright-startup.log`.
2. Confirm WebView2 is installed.
3. Confirm bundled dependencies were collected.
4. Delete partial `.vendor` or build temp folders if dependency installation short-circuited.
5. Re-run `.\build_exe.ps1`.
6. Rebuild the installer with `.\installer\build_installer.ps1`.

If Outlook refresh fails:

1. Confirm classic Outlook is installed and open.
2. Confirm the shared mailbox/folder exists: `NYCWA_Reservations > Inbox`.
3. Confirm `pywin32` was bundled.
4. Use the VBA macro fallback only when direct COM import is unavailable.

If classifier imports fail in the EXE:

1. Confirm PyInstaller collects sklearn/scikit_learn/joblib/threadpoolctl.
2. Confirm hidden imports for sklearn C extensions remain in `build_exe.ps1`.
3. Rebuild and rerun `/api/health`.

## Do Not Commit

- `dist\ReplyRight.exe`
- `dist\.env`
- `dist\data\*`
- local SQLite databases
- startup logs
- build folders
- vendored dependencies
- secrets
