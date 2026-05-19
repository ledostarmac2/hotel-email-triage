# Current Situation Report

Last updated: 2026-05-19 (Session 5)

## Status: PySide6 Phase 1 COMPLETE — Phase 2 (packaging) NOT STARTED

---

## Where we are

### Done

**PySide6 Phase 1 — full native Qt shell (commit 493803e)**
- `pywebview` + `pythonnet` removed; `PySide6>=6.7` added to `requirements.txt`
- `run_desktop.py` wired to `_open_qt_window`
- All screens written and wired:
  `api_client.py`, `app.py`, `theme.py`, `sidebar_nav.py`, `filter_bar.py`,
  `conversation_list.py`, `conversation_detail.py`, `login_window.py`, `main_window.py`
- All `ApiClient` endpoints verified against `outlook_dashboard/main.py` — 100% match
- FastAPI backend untouched
- 485 tests passing, 0 failures

**main branch — v0.1.2 released 2026-05-19**
- Admin login fixed end-to-end (Supabase + local SQLite fallback)
- `config.py` bug fixed: blank `SQLITE_DB_PATH` no longer crashes startup
- All runtime GitHub secrets in place; installer .env bakes them correctly

### NOT done (blockers to merge and release v0.1.3)

| # | Item | File | Owner |
|---|---|---|---|
| 1 | `build_exe.ps1` still vendorizes pywebview/pythonnet | `build_exe.ps1` | Claude |
| 2 | PyInstaller flags reference webview/clr/pythonnet | `build_exe.ps1` | Claude |
| 3 | `.iss` installer checks/downloads WebView2 | `installer/replyright_setup.iss` | Claude |
| 4 | Admin panel widget missing | `replyright_qt/widgets/admin_panel.py` | Claude |
| 5 | Branch diverged from main (missing v0.1.2 fixes to build.yml, config.py) | — | Claude |

---

## Phase breakdown

### Phase 1 — Qt shell  ✅ COMPLETE

### Phase 2 — Packaging  ❌ CRITICAL PATH

`build_exe.ps1` and `replyright_setup.iss` still reference the old WebView2/pywebview
stack. Nothing will build or install correctly until this is fixed.

**build_exe.ps1 — exact changes:**
- Remove from `$runtimePackages`: `"pywebview>=4.4,<6"`, `"pythonnet"`, `"pywin32"`
- Add to `$runtimePackages`: `"PySide6>=6.7"`, `"requests"`
- Remove `.vendor` check keys: `"win32com"→pywin32`; add `"PySide6"→PySide6`, `"requests"→requests`
- Remove PyInstaller flags:
  `--collect-all webview`, `--collect-all pythonnet`,
  `--hidden-import webview.platforms.edgechromium`,
  `--hidden-import webview.platforms.winforms`,
  `--hidden-import clr`, `--hidden-import pythoncom`,
  `--hidden-import pywintypes`, `--hidden-import win32com.client`
- Add PyInstaller flags:
  `--collect-all PySide6`, `--collect-all replyright_qt`,
  `--hidden-import PySide6.QtCore`, `--hidden-import PySide6.QtWidgets`,
  `--hidden-import PySide6.QtGui`
- Delete `.vendor` directory before building (stale cache will break the new bundle)

**replyright_setup.iss — exact changes:**
- Remove `#define WebView2Url` line
- Remove `var DownloadPage: TDownloadWizardPage;` declaration
- Remove entire `[Code]` section (all WebView2 check/download functions:
  `IsWebView2Installed`, `GetDefaultDir` already moved inline, `InitializeWizard`,
  `NextButtonClick`, `DownloadPage` initialization)
- Keep `GetDefaultDir` as a simple inline function (it existed before WebView2 code)
- PySide6 ships its own Qt DLLs — no runtime prerequisite download needed

### Phase 3 — Admin panel  🔲 PENDING PHASE 2
Build `replyright_qt/widgets/admin_panel.py`. See HANDOFF_CLAUDE.md for full spec.

### Phase 4 — Rebase + merge + release  🔲 BLOCKED ON PHASES 2+3
1. `git rebase main` on `feat/pyside6-native-ui` (picks up config.py fix, build.yml secrets)
2. Merge to main
3. Tag `v0.1.3` → triggers GitHub Actions release (first PySide6 installer)

---

## Do not do (standing orders)

- Do not add `QWebEngineView` anywhere in `replyright_qt/`
- Do not import `pywebview` or `webview` in `replyright_qt/`
- Do not wire `replyright_kernel/` into production
- Do not commit real secrets
- Do not log raw email bodies
- Do not add reply sending
- Do not touch `app/` (inactive Next.js scaffold)
