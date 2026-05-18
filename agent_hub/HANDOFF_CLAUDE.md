# Handoff: Claude

Last updated: 2026-05-18 (Session 4)

## What Claude completed this session

### PySide6 migration — Phase 1 COMPLETE (branch: feat/pyside6-native-ui)

Commit: 493803e on `feat/pyside6-native-ui`

The full pywebview → PySide6 replacement is working. The FastAPI backend is
**untouched**. The Qt shell replaces the browser-based frontend and makes the
same HTTP calls to the local uvicorn server.

**Files written/replaced:**
- `replyright_qt/api_client.py` — `ApiClient` (requests) + `ApiWorker` (QThread)
- `replyright_qt/app.py` — `QApplication` factory, login→main→logout flow
- `replyright_qt/styles/theme.py` — Qt stylesheet (dark sidebar, light content)
- `replyright_qt/widgets/sidebar_nav.py` — Inbox/Urgent/VIP/Missing/Admin nav + logout
- `replyright_qt/widgets/filter_bar.py` — search + category/status/risk dropdowns + Sync
- `replyright_qt/widgets/conversation_list.py` — custom rows with sender/urgency/time
- `replyright_qt/widgets/conversation_detail.py` — thread, AI analysis, feedback, status
- `replyright_qt/windows/login_window.py` — fully wired (ApiWorker, loading state, errors)
- `replyright_qt/windows/main_window.py` — QSplitter layout, all signals wired
- `run_desktop.py` — `_open_window` (pywebview) → `_open_qt_window` (PySide6)
- `requirements.txt` — pywebview/pythonnet removed, `PySide6>=6.7` added
- `tests/test_pyside6_no_browser_engine.py` — updated guard assertion

**Tests:** 485 passed, 0 failures (excluding pre-existing secret hygiene failure
in `dist/ReplyRight/.env` — unrelated to this branch).

---

## Claude's next tasks

**Priority 1: PyInstaller packaging for PySide6**
- Verify `pyinstaller` builds correctly with PySide6 (Qt platform plugins, styles)
- PySide6 bundles are larger (~150 MB); update `build_exe.ps1` and `replyright_setup.iss`
- Test that the built exe launches without needing a separate PySide6 install

**Priority 2: Admin dashboard panel**
- The admin queue button shows in the sidebar for admin users but has no dedicated panel yet
- Build `replyright_qt/widgets/admin_panel.py` using `/api/admin/stats` endpoint
- Show: correction count, misclassification table, training queue, model health

**Priority 3: Merge PySide6 into main**
- **Update:** Gemini has cleared the v0.1.1 release on `main`. You are now unblocked to merge `feat/pyside6-native-ui` into `main`.
- After merge: delete pywebview/WebView2 references from all docs

**Priority 4: Remove dist/ReplyRight/.env leak**
- `dist/ReplyRight/.env` contains a real Anthropic API key (line 10)
- This is not version-controlled but it's sitting on disk and failing secret hygiene test
- User should delete or revoke that key; it should NOT be in dist/

---

## Standing constraints for Claude

- Do not add QWebEngineView to any file in `replyright_qt/`
- Do not import pywebview or webview in `replyright_qt/`
- Do not wire `replyright_kernel/` into production
- Do not commit real secrets
- Do not log raw email bodies
- Do not add reply sending
- Do not touch `app/` (inactive Next.js scaffold)
