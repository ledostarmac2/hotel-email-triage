# Task Board

Last updated: 2026-05-19 (Session 5)

## Claude

| Task | Status | Notes |
|---|---|---|
| PySide6 Qt shell — all screens | ✅ Done | commit 493803e |
| ApiClient — all endpoints wired | ✅ Done | 100% match verified vs main.py |
| pywebview/pythonnet removed from requirements | ✅ Done | PySide6>=6.7 added |
| run_desktop.py → Qt window | ✅ Done | _open_qt_window |
| 485 tests passing | ✅ Done | 0 failures |
| **build_exe.ps1 — remove pywebview/pythonnet, add PySide6** | ❌ TODO | See CURRENT_SITREP Phase 2 for exact changes |
| **replyright_setup.iss — remove WebView2 check/download** | ❌ TODO | Remove entire [Code] section WebView2 block |
| **admin_panel.py widget** | ❌ TODO | See HANDOFF_CLAUDE.md for spec |
| **Rebase onto main + merge** | ❌ TODO | After phases 2+3; picks up v0.1.2 config.py fix |
| Delete .vendor cache before PySide6 build | ❌ TODO | Part of build_exe.ps1 update |

## Codex

| Task | Status | Notes |
|---|---|---|
| bundled_secrets.py cleanup | ✅ Done | On main |
| /credentials-setup route | ✅ Done | On main |
| v0.1.2 released | ✅ Done | 2026-05-19 |
| No pending Codex tasks | — | |

## Sequencing

```
Phase 2 (build_exe.ps1 + .iss)
    └── Phase 3 (admin_panel.py)
            └── Rebase onto main
                    └── Merge feat/pyside6-native-ui → main
                                └── Tag v0.1.3 → GitHub Actions release
```

Phase 2 and 3 can be done in parallel by the same agent in one session.
Rebase must happen after both are done and tests pass.
