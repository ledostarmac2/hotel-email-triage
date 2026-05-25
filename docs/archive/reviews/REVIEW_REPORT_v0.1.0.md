> Historical archive. Do not use this as current project state. Use docs/CURRENT_STATE.md, docs/HANDOFF.md, and docs/V1_RELEASE_PLAN.md instead.

# ReplyRight v0.1.0 Review Report

## 1. Blocking issues
*   **Startup Race Condition:** The desktop app previously bound to a hardcoded port (8000). If that port was occupied by another application, or a previously crashed instance of ReplyRight, the `_wait_for_server` health check might falsely succeed (if the other app responded 200 OK or `urlopen` connected). This led to `pywebview` opening and displaying a "127.0.0.1 refused to connect" error while the backend crashed in the background due to `[Errno 98] Address already in use`.
*   **Missing Installer Artifact:** The `.github/workflows/build.yml` file only uploaded the bare `dist/ReplyRight.exe` as the primary release artifact, omitting the generated Inno Setup installer (`ReplyRightSetup.exe`). This resulted in an incomplete release lacking an uninstaller, desktop shortcut, and the crucial WebView2 bootstrapper.

## 2. Non-blocking issues
*   `build_exe.ps1` doesn't enforce the installer build locally, leaving the responsibility entirely to the developer or the CI pipeline.
*   The `pywebview` browser fallback text instructs users to open their browser manually but users could be confused if the background server crashes shortly after due to unforeseen issues.

## 3. Release risks
*   If the CI builds the bare EXE successfully but fails to build the installer, the release might still succeed silently with only the bare EXE. We added `if-no-files-found: error` in the workflow to mitigate this.

## 4. Installer risks
*   The Inno Setup compiler (`ISCC.exe`) relies on an external download (`winget` or direct HTTP) in `build_installer.ps1`. If those external URLs change or go down, the CI build will fail.

## 5. Startup/runtime risks
*   Ephemeral ports dynamically assigned may occasionally trigger Windows Firewall prompts on first run depending on the user's local network settings, though it is usually fine for loopback (`127.0.0.1`).
*   The `_wait_for_server` timeout is 15 seconds. If a heavily loaded machine is slow to spin up `uvicorn`, the user might encounter a startup error before the app opens.

## 6. Native UI migration risks
*   **PySide6/Qt Migration:** PySide6 is very heavy and would increase the installer size significantly. Migrating away from FastAPI/HTML would require rewriting all the UI rendering logic. Re-using the intelligence layer is possible, but rewriting the entire frontend in Qt is an extremely risky time sink.
*   **C#/.NET WPF/WinUI Migration:** Requires keeping Python as a backend background process (or completely rewriting the intelligence layer in C#). Keeping Python as a backend creates inter-process communication overhead and still requires bundling the Python runtime via PyInstaller.
*   **Least risky path:** Stick with `pywebview` and the HTML/JS frontend. It leverages WebView2 (already present on modern Windows machines) and requires no UI rewriting. It meets the non-browser "desktop app feel" requirement.

## 7. Privacy/security risks
*   `replyright-startup.log` and `replyright-runtime.log` correctly avoid logging raw email bodies and PII data (using `_RequestLogMiddleware` which omits request/response bodies).
*   No raw email bodies are logged. No API keys or Supabase credentials are exposed in the diagnostic logs.

## 8. Missing tests
*   Integration tests simulating `_wait_for_server` with an occupied port to ensure the error handling works.
*   End-to-end tests for the installer creation process to verify shortcuts and registry keys.
*   Tests verifying that dynamically allocated ports correctly populate the `/api/health` URL.

## 9. Recommended v0.1.1 emergency fixes
*   *(Applied)* Use dynamic ephemeral port allocation (`port=0`) in `run_desktop.py` to ensure the application always binds to an available, isolated port and prevents connection refused errors.
*   *(Applied)* Update the GitHub Actions workflow `build.yml` to build the Inno Setup installer and upload it as `ReplyRightSetup-{version}.exe` instead of `ReplyRight.exe`.

## 10. Recommended v0.2.0 migration direction
*   Do not migrate to `app/`. Remain local-first.
*   Maintain the FastAPI + `pywebview` architecture. Refine the frontend with better React/Vanilla CSS encapsulation rather than replacing it with a heavy native framework.
*   Enhance the Inno Setup installer with auto-update checking logic directly from the UI.

## 11. Recommended installer/release workflow
*   CI builds `ReplyRight.exe` using `build_exe.ps1`.
*   CI calls `installer/build_installer.ps1` which packages the EXE into `ReplyRightSetup.exe`.
*   The release job renames `ReplyRightSetup.exe` to include the release tag version and uploads it as the primary GitHub Release asset.

## 12. Files likely needing changes
*   `run_desktop.py` (Completed)
*   `.github/workflows/build.yml` (Completed)

## 13. Specific patches Codex should make
*   No further patches needed; the emergency port allocation and CI workflow fixes have been fully authored and committed.

## 14. Things not to touch
*   Do not add automatic reply sending.
*   Do not migrate to `app/`.
*   Do not wire `replyright_kernel/` into production.
*   Do not alter logging configurations to expose email bodies.
