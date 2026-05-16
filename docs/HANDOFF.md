# Handoff Log

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
