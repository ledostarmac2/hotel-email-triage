# ReplyRight Installer Strategy

Last updated: 2026-05-18

## Position

ReplyRight releases must be installer-first.

The primary GitHub Release asset should be:

```text
ReplyRightSetup-v{version}.exe
```

The installed executable remains:

```text
ReplyRight.exe
```

A bare EXE may exist only as an internal CI artifact or optional portable package, and it must not be the default user download.

## Installer Technology

Use Inno Setup unless a stronger Windows deployment reason appears later.

Current files:

```text
installer/replyright_setup.iss
installer/build_installer.ps1
```

Build order:

```powershell
.\build_exe.ps1
.\installer\build_installer.ps1
```

Expected local output:

```text
installer\output\ReplyRightSetup-v0.1.1.exe
```

`build_exe.ps1` must use PyInstaller `--onedir`, producing:

```text
dist\ReplyRight\ReplyRight.exe
```

The installer bundles the full `dist\ReplyRight\*` folder and excludes local `.env`, runtime data, SQLite databases, and logs.

## Installer Requirements

- Installer display name: `ReplyRight Setup`
- Installed app display name: `ReplyRight`
- Installed executable: `ReplyRight.exe`
- Default per-user path: `%LOCALAPPDATA%\Programs\ReplyRight`
- Default machine-wide path when elevated: `%ProgramFiles%\ReplyRight`
- User can choose install path.
- Optional desktop shortcut.
- Start Menu shortcut.
- Windows uninstall entry.
- No Python installation required on target machine.
- No local `.env` required for first login; if no admin exists, first-run setup can create one through the bundled Supabase service-role configuration.
- Compatible with a fresh Windows 10/11 machine.
- Installer includes or handles WebView2 runtime.
- Installer uses ReplyRight icon where available.

## WebView2 Handling

While pywebview remains in v0.1.x, WebView2 is a runtime requirement. The Inno Setup script checks common WebView2 registry locations and downloads/runs Microsoft Edge WebView2 Runtime bootstrapper when missing.

If WebView2 is still unavailable at app startup, ReplyRight must show a controlled startup error dialog. It must not open a system browser fallback.

## GitHub Actions Requirements

The release workflow must:

1. Build the PyInstaller onedir app.
2. Build the Inno Setup installer.
3. Fail the release if installer creation fails.
4. Run the desktop startup helper tests and packaged `--health-smoke` before publishing.
5. Upload `ReplyRightSetup-v{version}.exe` as the primary release asset.
6. Avoid attaching raw `dist/ReplyRight/ReplyRight.exe` as the main user asset.

The build workflow may upload an installer artifact for CI verification:

```text
ReplyRightSetup-{commit}
```

## Current Workflow Status

`.github/workflows/build.yml` now builds:

- Windows lint/test
- PyInstaller EXE
- Inno Setup installer
- Docker health check
- Tag-based GitHub release with installer asset

The release body instructs users to download and run the setup installer, not the raw EXE.

## Optional Portable ZIP

An optional portable package is allowed later only if clearly labeled:

```text
ReplyRight-portable-v{version}.zip
```

Portable builds must remain secondary and must include a warning that the installer is preferred.

## Smoke Test Checklist

Before release:

- Build EXE.
- Build installer.
- Run `dist\ReplyRight\ReplyRight.exe --health-smoke`.
- Install on a clean or clean-ish Windows profile.
- Launch from Start Menu.
- Confirm no external browser opens.
- Confirm no WebView localhost refused page appears.
- Confirm `/healthz` succeeds after startup.
- Confirm login page loads.
- Confirm `dist\ReplyRight\data\replyright-startup.log` or installed runtime log contains safe diagnostics only.
- Confirm uninstall entry appears in Windows Apps.

## Known Follow-Up

Native UI migration should eventually remove the WebView2 dependency. Until then, the installer plus health-gated startup is the v0.1.1 release repair.
