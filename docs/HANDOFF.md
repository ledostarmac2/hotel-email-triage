# Handoff Log

## 2026-05-16 - Adaptive triage feedback and Supabase roadmap

Summary:

- Reworked conversation scoring so `/api/emails` groups threads and computes labels/urgency from the latest few messages instead of taking the highest stale urgency from any old email in the chain.
- Added latest-message body cleanup to ignore quoted Outlook history where possible, reducing false `Upset`, `Complaint`, and level 5 classifications.
- Added local adaptive feedback:
  - New `triage_feedback` SQLite table.
  - New `POST /api/emails/{email_id}/feedback` endpoint.
  - Conversation detail feedback box with correction notes plus optional urgency/owner controls.
  - Stored feedback applies immediately to the selected conversation and can guide similar future local messages.
- Added completed CCA/payment authorization handling so the app recognizes a completed form update as a Reservations task with concise steps: apply the form to the reservation and confirm completion.
- Tightened window/layout behavior: body no longer scrolls as the main page; the queue and right-side panels scroll independently, and the detail pane resets to the top when a new thread is selected.
- Lowered pywebview minimum window size to improve resizing behavior.
- Added `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` with the larger Supabase shared-learning architecture, staged AI pipeline, rule candidate concept, admin dashboard direction, privacy rules, and master future-agent prompt.
- Rebuilt `dist\ReplyRight.exe` and refreshed Desktop/Start Menu shortcuts.

Files changed:

- `run_desktop.py`
- `outlook_dashboard/ai.py`
- `outlook_dashboard/database.py`
- `outlook_dashboard/main.py`
- `outlook_dashboard/static/app.js`
- `outlook_dashboard/static/styles.css`
- `tests/test_ai_and_database.py`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG_AI.md`
- `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md`
- `docs/HANDOFF.md`

Verification:

- `python -m py_compile outlook_dashboard\ai.py outlook_dashboard\database.py outlook_dashboard\main.py run_desktop.py` - OK
- `python -m unittest tests.test_ai_and_database` - 9 tests OK
- `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` - 59 tests OK
- Synthetic API check: completed CCA thread with old quoted upset text classified as Positive, Reservations, urgency 3; feedback applied immediately.
- `.\build_exe.ps1` completed and built `dist\ReplyRight.exe`.
- Packaged health check succeeded. Current packaged data: 28 conversation groups; urgency distribution `2:14, 3:4, 4:7, 5:3`.

Immediate pickup for Claude:

- Launch the rebuilt Desktop shortcut and visually confirm the pywebview window resizes well.
- Click Refresh Inbox from the visible UI once and verify the queue still imports Outlook messages correctly.
- Select a thread far down the queue and confirm the right panel stays at the top while only the message list/right panels scroll.
- Spot-check formerly over-scored threads, especially completed CCA/payment authorization and friendly travel-agent replies.
- Enter one real feedback note on a misclassified conversation and confirm the label/urgency updates immediately.
- Browser automation was not completed because the Node REPL browser-control tool was not exposed in this Codex session; use manual UI verification or another browser-capable agent.

## 2026-05-16 - Outlook source-of-truth refresh and hotel triage rules

Summary:

- Implemented Outlook-source-of-truth cleanup: after successful Refresh Inbox, local SQLite rows whose `graph_message_id` is not in the current Outlook import are deleted. This removed mock/stale rows without mutating Outlook.
- Removed dashboard mock/demo seeding from the active app path, including the mock seed route and mock data fixture module.
- Added conversation grouping in the inbox API/UI. Queue rows now represent Outlook conversations, with `conversation_email_count`; detail view shows the conversation thread messages.
- Added `contact_type` analysis/migration: Internal, Group contact, Travel agency, Direct guest.
- Restricted department owners to actual operating departments: Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, All Departments. Removed Management as an owner and renamed escalation risk to `Leadership review required`.
- Reworked urgency scoring so arrival/check-in date is primary: same day/next day = 5, same week = 4, same month = 3, later this year = 2, next year/future = 1. Upset sentiment can raise urgency.
- Rebuilt `dist\ReplyRight.exe` and refreshed shortcuts.

Files changed:

- `.env.example`
- `README.md`
- `outlook_dashboard/ai.py`
- `outlook_dashboard/config.py`
- `outlook_dashboard/database.py`
- `outlook_dashboard/main.py`
- `outlook_dashboard/mock_data.py` (deleted)
- `outlook_dashboard/outlook_desktop.py`
- `outlook_dashboard/static/app.js`
- `outlook_dashboard/static/styles.css`
- `outlook_dashboard/taxonomy.py`
- `tests/test_ai_and_database.py`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG_AI.md`
- `docs/HANDOFF.md`

Verification:

- `python -m py_compile outlook_dashboard\ai.py outlook_dashboard\database.py outlook_dashboard\main.py outlook_dashboard\outlook_desktop.py` - OK
- `python -m unittest tests.test_ai_and_database` - 5 tests OK
- `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` - 59 tests OK
- `.\build_exe.ps1` completed and updated shortcuts.
- Packaged EXE refresh endpoint after final rebuild: fetched 46 Outlook emails, inserted 2, updated 44, analyzed 46, skipped 0, deleted 0 on the final pass, `launch_method=pywin32-com`. An earlier verification pass deleted 6 stale/non-current rows.
- Packaged inbox API after refresh: 28 conversation groups, max group size 5, owners limited to Concierge/Engineering/Front Desk/Housekeeping/Reservations on current data, no Management owner, no mock source rows.

Remaining work:

- User should click Refresh Inbox from the visible UI and visually confirm the conversation queue.
- Spot-check real-world arrival-date parsing and owner routing against live hotel patterns; add targeted rules for any recurring false classifications.

## 2026-05-16 - Refresh Inbox direct Outlook import

Summary:

- User confirmed the rebuilt pywebview `dist\ReplyRight.exe` opens, dashboard loads, and left tabs work.
- Refresh Inbox initially failed with PowerShell CLIXML wrapping VBScript/COM macro-call errors. Further testing showed Outlook's COM `Application` object does not expose `Run` here (`438 Object doesn't support this property or method`), so the macro-trigger approach was replaced.
- Implemented direct read-only Outlook import via `pywin32`:
  - Connects to classic Outlook with `win32com.client.Dispatch("Outlook.Application")`.
  - Reads only `NYCWA_Reservations > Inbox`.
  - Saves local `.msg` copies under the configured app data export folder.
  - Normalizes messages in-process and returns them to FastAPI for SQLite upsert and local triage.
  - Keeps `outlook.exe /autorun macroName` only as a fallback when `pywin32` is unavailable.
- Updated `app.js` refresh success copy for direct import counts.
- Added `pywin32>=306` to requirements and build vendoring; added PyInstaller hidden imports for `pythoncom`, `pywintypes`, and `win32com.client`.
- Updated architecture/current-state/decision/changelog docs.
- Rebuilt `dist\ReplyRight.exe` and refreshed Desktop and Start Menu shortcuts.

Files changed:

- `outlook_dashboard/outlook_desktop.py`
- `outlook_dashboard/main.py`
- `outlook_dashboard/static/app.js`
- `requirements.txt`
- `build_exe.ps1`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG_AI.md`
- `docs/HANDOFF.md`

Verification:

- `python -m py_compile outlook_dashboard\outlook_desktop.py` - OK
- `python -m unittest tests.test_ai_and_database` - 2 tests OK
- Source-level direct import probe read 44 messages from `NYCWA_Reservations > Inbox`, skipped 0, and used `launch_method=pywin32-com`.
- Packaged EXE endpoint verification succeeded: fetched 44, inserted 44, analyzed 44, skipped 0, `launched_macro=false`, `launch_method=pywin32-com`.
- `.\build_exe.ps1` completed successfully and created `dist\ReplyRight.exe`, Desktop shortcut, and Start Menu shortcut.

Remaining work:

- User should click Refresh Inbox from the UI once to confirm the visible button path after command-line endpoint verification.
- If Refresh Inbox fails on another machine, first confirm classic Outlook is installed/open and `pywin32` was bundled; only then fall back to the VBA macro path.

## 2026-05-16 — Desktop launcher, UI polish, Outlook COM fix, build hardening

Summary:

- **Desktop window**: switched from Edge app-mode (`--app=http://...`) to **pywebview** (WebView2/edgechromium backend). `run_desktop.py` now calls `webview.start(gui="edgechromium")` and adds a pre-flight `import clr` check that raises a descriptive `RuntimeError` instead of a silent native crash if pythonnet is missing.
- **UI — blue color theme**: replaced every purple `#6f42c1` accent with `#1565c0` (matches logo). Hover/active email row changed from `#f7f4fc` to `#f0f5ff`.
- **UI — working sidebar tabs**: Inbox / Urgent / VIP / Missing Info tabs now filter the email list client-side via a `viewEmails()` switch in `app.js`. State tracks `currentView`; clicking a tab re-renders the list without a server round-trip.
- **UI — button cleanup**: removed "Run Local Triage" and "Load Demo" buttons from the top-bar. Only "Refresh Inbox" remains. Removed `processPending()`, `seedMock()`, and their `els` references from `app.js`.
- **Outlook COM fix**: replaced the PowerShell `$app.Run($macroName)` call (which fails because PowerShell wraps COM as typed `ApplicationClass` without `Run()`) with a VBScript file executed by `cscript.exe //NoLogo`. VBScript uses pure IDispatch late-binding where `ol.Run "MacroName"` works correctly. Error hints for macro security and missing macro are included in the thrown message.
- **Python SyntaxError fix**: the VBScript line `""$macroName"""` inside the PowerShell heredoc contained `"""` which terminated the Python `r"""..."""` raw string early. Fixed by switching to `r'''...'''`.
- **Macro timeout**: increased `_MACRO_TIMEOUT_SECONDS` from 30 → 180; added explicit `subprocess.TimeoutExpired` catch with a clear message.
- **build_exe.ps1 hardening**:
  - Auto-detects the first system Python that is NOT inside `.venv` or `.build-venv` (VS Code auto-activates project venvs which lack PyInstaller).
  - Handles Windows Defender EXE lock: tries `Remove-Item`; falls back to `Rename-Item` to `.exe.old`.
  - Added `--collect-all pythonnet` and `--collect-all outlook_dashboard` to bundle all submodules that static analysis misses.
  - Added `--hidden-import clr` to ensure pythonnet's C extension is included.
- A fresh `dist\ReplyRight.exe` was built successfully at end of session. Desktop and Start Menu shortcuts updated.

Files changed:

- `outlook_dashboard/outlook_desktop.py`
- `outlook_dashboard/static/styles.css`
- `outlook_dashboard/static/index.html`
- `outlook_dashboard/static/app.js`
- `run_desktop.py`
- `build_exe.ps1`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`

Verification:

- `python -c "import ast; ast.parse(open('outlook_dashboard/outlook_desktop.py').read())"` — Syntax OK.
- PyInstaller build completed: `Building EXE from EXE-00.toc completed successfully`.
- Desktop shortcut updated: `C:\Users\btarabocchia\OneDrive - Hilton\Desktop\ReplyRight.lnk`.

Remaining work (not yet verified by user):

- Launch `dist\ReplyRight.exe` and confirm pywebview window opens (WebView2 runtime must be installed — it ships with Windows 10/11 but confirm on target machines).
- Test "Refresh Inbox" with Outlook open and the VBA macro installed to confirm VBScript IDispatch path works.
- Confirm Outlook macro security settings permit `cscript.exe` invocation (Trust Center → Macro Settings → Enable all macros, or sign the macro).
- If pywebview window fails: check `dist\data\replyright-startup.log` for the clr/pythonnet error; consider whether `.vendor` needs to be deleted and rebuilt to pick up pythonnet.


## 2026-05-16 — Semantic Kernel orchestration layer

Summary:

- Added `replyright_kernel/` Python package: Semantic Kernel boilerplate with three native plugins (PriorityTriagePlugin, ExecutiveSummaryPlugin, AuditCompliancePlugin), engine factory, plugin registry with labelled extension points for future Graph/CRM plugins, and an async four-step demo pipeline.
- All local plugins run with zero LLM cost; only the draft generation step calls the LLM through SK.
- 59 new tests (unit + integration with mocked LLM). Original 2 dashboard tests unaffected.
- Added `semantic-kernel>=1.15,<2` to requirements.txt and `KERNEL_LOG_LEVEL` to `.env.example`.
- Updated docs/CURRENT_STATE.md, docs/HANDOFF.md, docs/DECISIONS.md, docs/CHANGELOG_AI.md.

Files changed:

- `replyright_kernel/__init__.py`
- `replyright_kernel/settings.py`
- `replyright_kernel/engine.py`
- `replyright_kernel/registry.py`
- `replyright_kernel/demo.py`
- `replyright_kernel/plugins/__init__.py`
- `replyright_kernel/plugins/priority_triage.py`
- `replyright_kernel/plugins/executive_summary.py`
- `replyright_kernel/plugins/audit_compliance.py`
- `tests/test_kernel_plugins.py`
- `tests/test_kernel_orchestration.py`
- `requirements.txt`
- `.env.example`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG_AI.md`

Verification:

- `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` — 59 tests OK
- `python -m unittest tests.test_ai_and_database` — 2 tests OK (no regression)

Remaining work:

- Wire `replyright_kernel` into the FastAPI `ai.py` path when ready (replace or supplement the on-demand OpenAI call).
- Implement GraphMailPlugin when Entra app registration is available.
- Implement CRMLookupPlugin when a CRM integration is approved.
- Set `OPENAI_MODEL=gpt-5.5` in `.env` and run `python -m replyright_kernel.demo` for a live end-to-end test once the model is available on the account.



## 2026-05-16

Summary:

- Set up the multi-agent handoff documentation framework.
- Documented the active ReplyRight architecture, current state, risks, and decisions.
- Preserved the distinction between the active Python/FastAPI app and the older Next.js scaffold.
- Kept the app read-only for Outlook.
- Made two portability/build hygiene edits: removed obsolete `pywebview` vendoring from `build_exe.ps1`, and changed the Outlook macro export path to the current user's Documents folder instead of a workstation-specific repo path.

Files changed:

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG_AI.md`
- `.codex/config.toml`
- `ARCHITECTURE.md`
- `.gitignore`
- `build_exe.ps1`
- `outlook_dashboard/static/outlook_refresh_macro.bas`

Verification:

- Repository inspection completed.
- `python -m unittest tests.test_ai_and_database` passed.
- Full commit/push status should be recorded in the final assistant response for this work.

Remaining work:

- Rebuild and launch-test `dist\ReplyRight.exe` after these source edits.
- Confirm the latest VBA macro works in classic Outlook on both work and home machines.
- Confirm OpenAI key/model behavior once credentials are available.
