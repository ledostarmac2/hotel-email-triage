# Handoff: Claude

Last updated: 2026-05-19 (Session 5)

---

## Context

Branch: `feat/pyside6-native-ui`
Phase 1 (Qt shell) is complete and verified. You own everything remaining before
this branch can merge to main and ship as v0.1.3.

Do NOT switch to main. Do NOT merge until all three tasks below are done and
`python -m pytest tests/ -x` passes.

---

## Task 1 — Update build_exe.ps1 for PySide6  (CRITICAL PATH)

File: `build_exe.ps1`

The script still vendors pywebview/pythonnet and passes their PyInstaller flags.
Replace with PySide6 equivalents.

**`$runtimePackages` array — remove:**
```
"pywebview>=4.4,<6"
"pythonnet"
"pywin32"
```

**`$runtimePackages` array — add:**
```
"PySide6>=6.7"
"requests"
```

**`$vendorChecks` hashtable — remove:**
```
"win32com" = "pywin32"
```

**`$vendorChecks` hashtable — add:**
```
"PySide6" = "PySide6"
"requests" = "requests"
```

**Before the `New-Item ... $vendorPath` block, add a stale-cache wipe:**
```powershell
# PySide6 replaces pywebview/pythonnet — wipe stale vendor cache if it contains old packages
if ((Test-Path $vendorPath) -and (Test-Path (Join-Path $vendorPath "webview"))) {
    Write-Host "Removing stale vendor cache (pywebview detected)"
    Remove-Item $vendorPath -Recurse -Force
}
```

**PyInstaller invocation — remove these flags entirely:**
```
--collect-all webview
--collect-all pythonnet
--hidden-import webview.platforms.edgechromium
--hidden-import webview.platforms.winforms
--hidden-import clr
--hidden-import pythoncom
--hidden-import pywintypes
--hidden-import win32com.client
```

**PyInstaller invocation — add these flags:**
```
--collect-all PySide6
--collect-all replyright_qt
--hidden-import PySide6.QtCore
--hidden-import PySide6.QtWidgets
--hidden-import PySide6.QtGui
```

---

## Task 2 — Strip WebView2 from the Inno Setup installer  (CRITICAL PATH)

File: `installer/replyright_setup.iss`

PySide6 ships its own Qt DLLs inside the PyInstaller bundle. No WebView2 runtime
is needed. The `[Code]` section that downloads WebView2 must be removed entirely.

**Remove the `#define` line:**
```
#define WebView2Url "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
```

**Remove the `var` declaration at the top of `[Code]`:**
```pascal
var
  DownloadPage: TDownloadWizardPage;
```

**Remove the entire `[Code]` section** except `GetDefaultDir`, which must be kept
as a bare function (it is referenced by `DefaultDirName={code:GetDefaultDir}`):
```pascal
[Code]
function GetDefaultDir(Param: String): String;
begin
  if IsAdminInstallMode then
    Result := ExpandConstant('{autopf}\ReplyRight')
  else
    Result := ExpandConstant('{localappdata}\Programs\ReplyRight');
end;
```

Everything else in `[Code]` (`IsWebView2Installed`, `InitializeWizard`,
`NextButtonClick`, download page setup) — delete it.

---

## Task 3 — Build admin_panel.py widget

File: `replyright_qt/widgets/admin_panel.py`

The sidebar already has an "Admin" queue button for admin-role users
(`sidebar_nav.py`). When it is clicked, `main_window.py` receives
`queue_changed("admin")` but currently loads the email list like any other queue.
Replace that with a dedicated admin panel.

**What to build:**
A `QWidget` subclass `AdminPanelWidget` that calls `/api/admin/stats` on load and
renders a summary dashboard. Wire it into `main_window.py` so that when
`self._current_queue == "admin"` the splitter's right pane shows
`AdminPanelWidget` instead of `ConversationDetailWidget`.

**`/api/admin/stats` response shape** (from `outlook_dashboard/main.py`):
```json
{
  "total_emails": int,
  "pending_review": int,
  "high_priority": int,
  "avg_confidence": float,
  "correction_count": int,
  "correction_rate": float,
  "low_confidence_count": int,
  "overview": { ... },
  "recent_corrections": [ ... ],
  "misclassification_drilldowns": [ ... ]
}
```

**Minimum viable panel:**
- Four stat cards in a 2×2 grid: Total Emails, Pending Review, High Priority, Corrections
- A "Training queue" count (low_confidence_count)
- A "Refresh" button that re-fetches stats
- Use `ApiWorker` for the fetch — never block the main thread
- Match the existing dark stylesheet (see `replyright_qt/styles/theme.py`)

**Wire into main_window.py:**
In `_build_ui`, construct both `ConversationDetailWidget` and `AdminPanelWidget`.
In `_on_queue_changed`, show the right one based on `queue == "admin"`.
Use `QStackedWidget` or simply `show()`/`hide()` on the two panels.

---

## Task 4 — Rebase and merge

After Tasks 1–3 pass `pytest -x`:

```powershell
git rebase main
# resolve any conflicts (build.yml and config.py diverged — take main's version)
git push origin feat/pyside6-native-ui --force-with-lease
```

Then open a PR from `feat/pyside6-native-ui` → `main`, or merge directly if
the user authorizes it. After merge, tag `v0.1.3`.

---

## Constraints

- No `QWebEngineView` anywhere in `replyright_qt/`
- No `pywebview` / `webview` imports in `replyright_qt/`
- No real secrets committed
- Do not touch `app/` (inactive Next.js scaffold)
- Do not wire `replyright_kernel/` into production
- Do not add reply sending
- Do not log raw email bodies
