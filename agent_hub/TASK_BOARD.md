# Task Board

Last updated: 2026-05-19 (Session 6)

## Claude

| Task | Status | Notes |
|---|---|---|
| PySide6 Qt shell — all screens | ✅ Done | commit 01cda15 |
| ApiClient — all endpoints wired | ✅ Done | 100% match verified vs main.py |
| pywebview/pythonnet removed from requirements | ✅ Done | PySide6>=6.7 added |
| run_desktop.py → Qt window | ✅ Done | _open_qt_window |
| 499 tests passing | ✅ Done | 0 failures |
| build_exe.ps1 — remove pywebview/pythonnet, add PySide6 | ✅ Done | commit eb971d9 |
| replyright_setup.iss — remove WebView2 check/download | ✅ Done | commit eb971d9 |
| admin_panel.py widget | ✅ Done | commit e93b530 |
| Wire admin_panel into main_window.py (QStackedWidget) | ✅ Done | commit e93b530 |
| Delete .vendor cache before PySide6 build | ✅ Done | Part of build_exe.ps1 update |
| Rebase onto main | ✅ Done | Picked up config.py fix + build.yml secrets |
| auth.py ensure_admin Supabase fallback | ✅ Done | commit 4578992 |
| Bump version to 0.1.3 | ✅ Done | __init__.py + pyproject.toml + .iss |
| **Merge feat/pyside6-native-ui → main** | ❌ TODO | After version bump committed |
| **Tag v0.1.3** | ❌ TODO | After merge; triggers GitHub Actions release |

## Codex

| Task | Status | Notes |
|---|---|---|
| bundled_secrets.py cleanup | ✅ Done | On main |
| /credentials-setup route | ✅ Done | On main |
| v0.1.2 released | ✅ Done | 2026-05-19 |
| No pending Codex tasks | — | |

## Sequencing

```
Phase 2 (build_exe.ps1 + .iss)        ✅
    └── Phase 3 (admin_panel.py)       ✅
            └── Rebase onto main       ✅
                    └── Merge feat/pyside6-native-ui → main   ← NEXT
                                └── Tag v0.1.3 → GitHub Actions release
```
