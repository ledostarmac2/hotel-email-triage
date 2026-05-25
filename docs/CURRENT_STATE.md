# Current State

Last updated: 2026-05-25 (v1 safety + UI hardening — steps 4-8)

## Status

- Product name is ReplyRight.
- Current runnable app is `outlook_dashboard/` plus `run_desktop.py`.
- 2026-05-25 Docker CI restoration and training-workflow clarification:
  - Restored root `Dockerfile` and `docker-compose.yml` after the v0.5.0 cleanup removed them while `.github/workflows/build.yml` still runs the `docker-build` job with `docker build -t replyright-ci .`.
  - The Docker image runs the FastAPI server path (`outlook_dashboard.main:app`) on port 8000 and health-checks `/api/health`; it is for CI/server smoke, not the Windows desktop UI.
  - Added asset contract coverage so the Dockerfile/compose files cannot disappear while the CI workflow still expects them.
  - Clarified the training split in `AGENTS.md`, `docs/TRAINING_WORKFLOW.md`, `docs/V1_RELEASE_PLAN.md`, and `docs/ARCHITECTURE.md`: in-app training endpoints remain zero-credit and never call Claude/OpenAI/Google, while Codex/Claude may perform an explicit outside-the-app agent-assisted labeling/review pass only when Brian directly asks an agent to "train the model."
  - Validation passed: `python -m pytest tests/test_asset_contract.py tests/test_pipeline_docs_contract.py -q --timeout=60`. Local Docker runtime is not installed on this PC, so the actual image build must be verified by GitHub Actions or on a machine with Docker.
  - Follow-up release target is `0.5.1`, containing the Docker CI restoration and training-workflow clarification on top of the `0.5.0` anchor cleanup.
- 2026-05-25 local classifier training pass:
  - Claude completed the primary Completed Request training run before Codex began its own cycle: imported 1000, labeled 983, uploaded 983, skipped 17, failed 0, purged 1000 local completed-request rows; no in-app external AI providers were called.
  - Claude performed an agent-assisted review/approval pass on sanitized examples and retrained the local classifier to version `20260525T200024Z`.
  - Codex verified the active local classifier status: trained on 616 examples at train time (578 Supabase + 38 local/bootstrap), targets `urgency`, `owner`, and `category`, no warnings, `needs_training=false`; CV accuracy is urgency 56.65%, owner 73.54%, category 52.92%.
  - Codex started a duplicate import before seeing Claude's completed-training note, then stopped the lingering Python process after the shell timeout. Codex later found and stopped an additional duplicate "pipeline batch 2" process. Current cumulative local Completed Request log status is processed 2833, uploaded/labeled 2248, dumped 540, skipped 45, failed 0.
  - Supabase count check after stopping duplicate processes showed 1344 total training examples, 476 reviewed/agent-approved, and 868 unreviewed. Do not bulk-approve the remaining unreviewed queue without a controlled review pass.
  - Synthetic beta after training passed 25/25 with the same known same-day-arrival category-hint gap.
- 2026-05-25 KYC Selenium packaging repair:
  - KYC Auto failed at runtime with `No module named 'selenium'` because the KYC automation script is loaded dynamically from bundled data, so PyInstaller did not see its Selenium imports.
  - Added Selenium to runtime dependencies and PyInstaller vendor/collection rules; added explicit Selenium imports in `outlook_dashboard/kyc/automation.py` so the frozen app bundles the modules needed by the dynamic automation script.
  - Follow-up KYC wiring audit found and fixed a second packaged-runtime issue: the frozen wrapper could search for `.external\KYC-Auto\Files\kyc_automation.py` under `_internal\outlook_dashboard\` instead of the PyInstaller runtime root. `outlook_dashboard/kyc/automation.py` now searches frozen and source runtime roots, including `sys._MEIPASS`.
  - Strengthened `run_desktop.py --kyc-smoke` so it validates Selenium, locates the bundled KYC automation source file, and imports the dynamic KYC module without launching Edge or the full UI.
  - Validation passed: `python -m py_compile run_desktop.py outlook_dashboard\kyc\automation.py`, `python -m pytest tests/test_installer_contract.py tests/test_kyc_backend.py tests/test_kyc_service_full.py -q --timeout=60`, `.\build_exe.ps1`, `.\dist\ReplyRight\ReplyRight.exe --kyc-smoke`, and `.\dist\ReplyRight\ReplyRight.exe --health-smoke`.
  - Rebuilt the onedir app at `dist\ReplyRight\ReplyRight.exe`; build info now reports commit `4ccd0cd6`, build date `2026-05-25T17:48:23Z`, version `0.4.0`.
- 2026-05-25 auto-refresh repair:
  - The previous native UI work fixed the Refresh Inbox button path but did not automatically call it after login. `replyright_qt/windows/main_window.py` now performs the initial local inbox load and then triggers the same read-only Outlook refresh once per app session through `QTimer.singleShot(...)`.
  - Added a regression check in `tests/test_pyside6_no_browser_engine.py` so the native startup auto-refresh wiring is not dropped again.
  - Validation passed: `python -m py_compile replyright_qt\windows\main_window.py`, `python -m pytest tests/test_pyside6_no_browser_engine.py -q --timeout=60`, `git diff --check` with line-ending warnings only, `.\build_exe.ps1`, and `.\dist\ReplyRight\ReplyRight.exe --health-smoke`.
  - Rebuilt the onedir app at `dist\ReplyRight\ReplyRight.exe`; build metadata now reports commit `4ccd0cd6`, build date `2026-05-25T16:40:12Z`, version `0.4.0`.
- 2026-05-25 Codex review/fix after Claude steps 4-8:
  - Reviewed Claude's classifier/admin hardening and found a rollback/status integrity issue: previous model rollback restored the model blob without restoring the matching metadata, and classifier status checked rollback availability through an unmanaged SQLite context.
  - Fixed `outlook_dashboard/local_classifier.py` so model metadata is rotated with the model bundle, training persists Supabase/local source counts in metadata, classifier status uses managed SQLite access, and rollback only reports available when both previous model and previous metadata are present.
  - Tightened deployment diagnostics so secret-looking values are actively scrubbed from response values, not merely warned about.
  - Added regression tests in `tests/test_diagnostics_contract.py` proving rollback restores previous metadata, unsafe model-only rollback is rejected, training source counts survive into persisted metadata, and secret-like diagnostics values are redacted.
  - Rebuilt the onedir app at `dist\ReplyRight\ReplyRight.exe`; build metadata now reports commit `4ccd0cd6`, build date `2026-05-25T15:38:30Z`, version `0.4.0`.
  - Validation passed: full suite `1043 passed`, 6 existing `datetime.utcnow()` warnings, 35 subtests; `git diff --check` passed with line-ending warnings only; `.\build_exe.ps1` passed; `.\dist\ReplyRight\ReplyRight.exe --health-smoke` passed; `python scripts\synthetic_beta.py` passed 25/25 synthetic scenarios with the documented same-day urgency known gap.
- 2026-05-25 v1 safety + UI hardening (Claude steps 4-8):
  - **Step 4 — Automated safety guardrail tests** (`tests/test_safety_guardrails.py`, 102 tests): verifies Outlook read-only behavior in both import sources, that `triage_email()` never calls Claude/Anthropic at runtime, training export privacy (`body_redacted` only, no `body_text`/`sender_email`/`graph_message_id`), risk-class needs_review triggers, and all four `needs_review` compound boolean conditions.
  - **Step 5 — Classifier/admin hardening**: added `get_classifier_status()` and `rollback_model()` to `outlook_dashboard/local_classifier.py`; exposed `GET /api/admin/classifier/status` and `POST /api/admin/classifier/rollback` in `outlook_dashboard/main.py`; enriched `GET /api/admin/deployment/diagnostics` with `examples_at_train_time`, `examples_supabase`, `examples_local`, `accuracy_per_target`, and a paranoid secret-sentinel scan that appends a warning if any of `service_role`, `api_key`, or `eyJ` appear in the serialised diagnostics output.
  - **Step 6 — Synthetic beta simulation** (`scripts/synthetic_beta.py`): 25 deterministic hotel email scenarios covering all 14 taxonomy categories; produces a triage report to stdout and `docs/reports/synthetic_beta_report.json`; 25/25 scenarios pass; 1 known v1 gap documented (same-day arrival urgency stays at 2 instead of 4+ because `compute_urgency()` does not yet handle the "Urgent same-day arrival" category hint).
  - **Step 7 — UI safety polish**: `replyright_qt/widgets/conversation_list.py` now shows a red "Review" badge in the right column of every conversation row where `needs_review=True`; `replyright_qt/widgets/conversation_detail.py` now shows a red "Needs Human Review" banner (with inline reason: low confidence %, risk flags, high-risk category) at the top of each detail panel when `needs_review=True`, adds a "Classification Source" metric card (heuristic / local ML classifier / OpenAI / Claude AI) in the triage grid row 3, and renders risk flags with a red `risk-chip` style instead of the generic blue chip; `replyright_qt/styles/theme.py` has the new CSS for all three: `badge-needs-review`, `needs-review-banner`, `risk-chip`, `risk-flags-label`.
  - **Step 8 — Diagnostics contract tests** (`tests/test_diagnostics_contract.py`, 25 tests): verifies response shape/types for `/api/admin/deployment/diagnostics` (all top-level sections + new classifier fields), `/api/admin/classifier/status` (all required keys + types + no-model state), `/api/admin/classifier/rollback` (rolled_back bool, version_id, reason; no-model returns `rolled_back=False`), and secret-redaction invariants (no `eyJ` JWT prefix in diagnostics output).
  - **Full test suite: 1039 passed, 0 failures, 6 existing `datetime.utcnow()` deprecation warnings, 35 subtests.**
- 2026-05-25 v1 readiness consolidation:
  - Added `docs/V1_RELEASE_PLAN.md` as the v1 gate/checklist document and source-of-truth map for scattered roadmap, pipeline, classifier, deployment, and operations docs.
  - Reconciled version drift: runtime package, FastAPI metadata, `pyproject.toml`, and the Inno Setup fallback version now align at `0.4.0`.
  - Added version consistency tests so future package, installer, FastAPI, updater fallback, and build metadata generation drift fails in CI.
  - Converted `training/README.md` from an obsolete Completed Requests dump/Claude extraction runbook into a pointer to the canonical docs.
  - Marked `docs/coordination/README.md` and all archived planning/migration/review Markdown files as historical, with regression tests to keep stale docs from becoming implicit source-of-truth again.
  - Reaffirmed the current origin training contract: in-app training endpoints are zero-credit and must not call Claude/Anthropic, OpenAI, or Google AI. External human/agent labeling can happen outside the app and flow back through reviewed labels.
  - Updated `AGENTS.md` to include the v1 plan in broad-work first reads and to state that Claude is not used by bulk refresh or in-app training endpoints.
  - Validation passed: version/doc/training targeted tests, safety guardrails, archive/source-of-truth checks, compile checks, `git diff --check`, and the full suite (`1039 passed`, 6 existing `datetime.utcnow()` warnings, 35 subtests).
- 2026-05-20 native icon polish:
  - Sidebar navigation now uses polished PNG image assets in `replyright_qt/resources/icons/` instead of the temporary native line drawing widget. Icons are themed for the dark ReplyRight sidebar and bundled through the existing `--collect-all replyright_qt` packaging path.
  - Conversation list selection now marks the actual row widget as selected and lets QSS paint a subtler row surface, reducing the blocky text-highlight look while keeping labels transparent.
  - DO-178C starter artifacts exist under `docs/compliance/` and `tests/test_do178c_compliance.py`; Claude owns that compliance/test-suite lane, while Codex is focused on UI.
  - Validation passed: Qt compile check, targeted PySide6/sidebar tests, offscreen Qt smoke for icon loading plus selected-row styling, `.\build_exe.ps1`, and packaged `dist\ReplyRight\ReplyRight.exe --health-smoke`.
- 2026-05-20 v0.4.0 CI/release repair:
  - Fixed the GitHub Actions lint failure in `tests/test_completed_training_pipeline.py` by restoring the Completed Requests training pipeline to the documented zero-credit sanitized-upload path.
  - `outlook_dashboard/completed_training_pipeline.py` now imports read-only completed Outlook messages, labels them with local heuristics, builds redacted examples through the shared training helper, uploads sanitized records, and reports `external_ai_used=false`.
  - Restored the PySide6 `Needs Review` queue and `QUEUES` compatibility export so v1 queue tests and native navigation agree with the API client's `needs_review=true` mapping.
  - Updated the updater release test fixture to use a future semantic version now that app source is `0.4.0`.
  - Added root SQLite/DB ignore patterns and removed the generated local classifier DB artifact from staging; runtime model/database files remain local-only.
  - Removed the stale release workflow check that required `dist\ReplyRight\.env`; the current installer excludes `.env` and ships `sample.env` only.
  - Validation passed: targeted training/updater/sidebar tests and full suite (`798 passed`, 6 existing `datetime.utcnow()` warnings, 35 subtests).
  - Zero-credit local classifier training was started against the default runtime SQLite DB after the fix: 38 local/bootstrap examples, targets `urgency`, `owner`, and `category`, model version `20260520T195713Z`. No external AI providers were called.
- 2026-05-20 native UI repair/polish:
  - The PySide6 inbox refresh action now calls the proven read-only Outlook desktop import endpoint (`/api/outlook-desktop/export-inbox`) instead of the Graph sync endpoint, preserving the current classic Outlook COM import path.
  - Native sidebar queue views now filter Inbox/Urgent/VIP/Missing Info in the Qt client and auto-select the first visible conversation after loading.
  - The native detail pane now reads `conversation_messages` from the API, renders triage metrics, risk/missing-info chips, next steps, message cards, suggested draft text, status controls, and structured correction feedback.
  - Native feedback submission now includes the required `feedback_text` and supports urgency, category, owner, contact type, status, summary quality, and reply quality corrections using the centralized taxonomy values.
  - Native status updates now use valid ReplyRight status labels and refresh the queue after a successful update.
  - Login/sidebar polish now uses the ReplyRight logo asset where available; the inbox toolbar was restyled around a clear `Refresh Inbox` action and visible refresh status.
  - The installer script now has cleaner app metadata, support/update URLs, and branded welcome/finish copy while keeping the installer-first release path.
  - Validation passed: PySide6 compile/import smoke, offscreen Login/MainWindow construction, targeted Qt/API/installer checks, and the full suite (`729 passed`, 5 existing `datetime.utcnow()` warnings, 35 subtests).
- 2026-05-20 native UI visual repair follow-up:
  - Reworked the PySide6 theme into a light/dark stylesheet factory and added a Settings page with theme switching, password reset request, and basic workflow/safety settings.
  - Restyled the sidebar toward the target dark navy dashboard: logo/tagline, user card, queue/admin sections, queue count badges, Waldorf Astoria footer, and a subtler read-only status badge.
  - Restyled the login logo presentation by placing the ReplyRight mark on a navy brand panel so it remains legible on the white sign-in card.
  - KYC Auto now opens as a separate PySide6 popup from the sidebar. The active surface is automation-first: KYC username, KYC password, on-phones checklist, and three actions only: Start Timer, Cancel, and Run Now. It no longer shows due dates, inspection history, completed-by, snooze, skip, or manual reminder controls.
  - Hardened `MainWindow` and `ConversationDetailWidget` worker lifetime handling so rapid queue changes such as Missing Info do not destroy active `QThread` workers.
  - Changed KYC automation missing-module failures to a clean user-facing message and updated `build_exe.ps1` to bundle the local KYC automation file and Edge driver when present.
  - Validation passed: targeted Qt/API/installer checks, offscreen Qt popup smoke, full suite (`729 passed`, 5 existing `datetime.utcnow()` warnings, 35 subtests), `.\build_exe.ps1`, and packaged `dist\ReplyRight\ReplyRight.exe --health-smoke`.
  - Follow-up visual repairs after Brian review: conversation row labels now paint transparent backgrounds to remove gray text blocks; sidebar uses a native Qt line-icon set instead of text stand-ins; Settings can choose/clear a profile photo; the sidebar has a Waldorf Astoria text/monogram footer.
  - Right detail pane follow-up: horizontal scrolling is disabled, message/draft bodies wrap to panel width, the status/action controls and triage cards are more compact, and raw Exchange distinguished-name sender strings are hidden from the header.
- 2026-05-19 login incident repair:
  - Supabase Auth is authoritative when `SUPABASE_URL` and `SUPABASE_KEY` are configured; local SQLite login is now only for unconfigured/no-key fallback.
  - Local PyInstaller onedir builds now look for the repo-root `.env` when `dist\ReplyRight\.env` is absent, so Brian's local test EXE can use the configured Supabase credentials without copying secrets into `dist`.
  - The native PySide6 sign-in screen was restyled with Qt Fusion, a polished card layout, corrected transparent labels, a restored "Remember email" checkbox backed by `QSettings`, and clearer Supabase/read-only copy.
  - Source-level Supabase admin repair and password login were verified with the configured `.env` without printing secret values.
- KYC Auto backend absorption has started:
  - `outlook_dashboard/kyc/` now provides the integrated KYC Inspections backend module.
  - FastAPI exposes authenticated `/api/kyc/*` endpoints for configuration, current reminder status, event creation, acknowledge, snooze, complete, skip, and history.
  - SQLite now creates `kyc_settings`, `kyc_inspection_events`, `kyc_acknowledgements`, and `kyc_audit_log`.
  - KYC actions are recorded in both the module audit log and ReplyRight's shared `audit_logs`.
  - Supabase mirroring is best-effort for non-secret KYC settings/events when configured; SQLite remains the fallback/source of local continuity.
  - The legacy KYC Auto Tkinter UI, standalone installer, Edge driver files, and Selenium automation were inspected but not copied into the active backend.
  - Backend verification: `python -m pytest tests/ --timeout=60` passed with 503 tests, 5 existing `datetime.utcnow()` warnings, and 35 subtests.
- Repository cleanup is in progress:
  - Root-level historical planning/review docs moved to `docs/archive/`.
  - Migration/release-blocker docs moved to `docs/archive/migration/`.
  - Multi-agent coordination docs moved from `agent_hub/` to `docs/coordination/`; `agent_comms/` remains the live message channel.
  - Third-party reference repos are removed from git tracking and preserved locally under ignored `.external/reference/`.
  - The dropped standalone KYC Auto bundle is preserved locally under ignored `.external/KYC-Auto/`.
  - Old generated binaries such as `dist2/ReplyRight.exe` and the temporary `new_dependencies.txt` handoff file are removed from tracking.
- v0.1.0 is blocked as a user release because the downloaded app could show a WebView/Edge `127.0.0.1 refused to connect` page and the release path was not installer-first enough for real users.
- v0.1.1 repair is now in source:
  - `GET /healthz` is public and used by the desktop launcher before opening pywebview.
  - `run_desktop.py` waits up to 30 seconds for backend health before creating the window.
  - Browser fallback was removed; startup failure now shows a controlled ReplyRight error dialog with `replyright-startup.log`.
  - The launcher prefers configured `APP_PORT` and chooses a dynamic available port only if the preferred port is occupied.
  - `run_desktop.py --health-smoke` starts the packaged backend, verifies `/healthz`, and exits without opening WebView2.
  - `build_exe.ps1` now uses PyInstaller `--onedir` and outputs `dist\ReplyRight\ReplyRight.exe`.
  - The Inno Setup installer bundles the full `dist\ReplyRight\*` folder and excludes `.env`, runtime data, DBs, and logs.
  - First-run setup exists at `/setup` and `/api/auth/setup`; if no admin user exists and Supabase service-role config is available, the user can create the first admin without a local `.env`.
  - GitHub release workflow and updater now prefer `ReplyRightSetup-v{version}.exe` installer assets.
  - Source version is bumped to `0.1.1`.
- 2026-05-19 release/auth repair:
  - Fixed the CI failure in `tests/test_pyside6_no_browser_engine.py` by restoring the PySide6 scaffold contract: `replyright_qt/main_qt.py` now raises a `RuntimeError` if run directly, and `replyright_qt/windows/main_window.py` has a PySide6 import guard.
  - Native PySide6 auth/inbox/KYC shell files are present and the desktop launcher now opens Qt after FastAPI health succeeds. `--native` is retained as a compatibility no-op because Qt is the current shell.
  - Removed the user-facing credentials setup page from the desktop app. `/credentials-setup` now redirects to login, and `/api/auth/credentials-setup` is no longer an unauthenticated API-key writing endpoint.
  - End users must not be asked for Supabase, OpenAI, Google, Anthropic, or other API keys in the program. Runtime credentials must be supplied by deployment-time files, machine environment, or GitHub Actions release secrets.
  - GitHub Actions now opts JavaScript actions into Node 24 with `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`.
  - Fixed the release workflow rename step so tag builds no longer fail when Inno Setup already emitted the expected `ReplyRightSetup-v0.1.1.exe` filename.
  - Installer security audit now treats `innoextract` format incompatibility as a warning and still audits the staged `dist\ReplyRight` payload plus installer output.
  - Restored local SQLite authentication as a fallback for existing installed databases and fresh installs without Supabase service-role configuration. Supabase Auth is still used when configured; if unavailable or not configured, ReplyRight can authenticate local `users` rows and create local sessions.
  - First-run setup can now create a local SQLite admin when no admin exists and Supabase service-role configuration is absent. It still does not ask users for API keys.
  - Superseded by 2026-05-20 release security posture: the installer excludes `.env`; runtime credentials must be provisioned outside the installer.
  - Startup now always creates/repairs the configured `REPLYRIGHT_ADMIN_EMAIL` / `REPLYRIGHT_ADMIN_PASSWORD` account when those values are present, instead of redirecting to first-run setup first.
  - Release CI now treats `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` as required installer runtime secrets.
- 2026-05-19 massive test expansion:
  - Added 225 new tests across three new files; full suite now at 729 tests, 0 failures.
  - `tests/test_triage_real_world.py` (112 tests): real hotel email scenarios covering VIP, billing, ADA, same-day arrival, complaints, CCA, concierge, rate inquiry, consortia, internal, group blocks, sentiment detection, and edge cases.
  - `tests/test_api_full_coverage.py` (60 tests): full FastAPI endpoint coverage — auth, emails, KYC lifecycle via API, admin, import/export, rule candidates, rate limiting.
  - `tests/test_kyc_service_full.py` (53 tests): KYC service unit tests — settings, event CRUD, acknowledge/snooze/complete/skip lifecycle, overdue/strict mode, missed count, escalation, history, repository methods.
  - Fixed real bug: `needs_credentials_setup` was missing from `outlook_dashboard/main.py` import block, causing NameError at `/api/auth/startup-state`.
- Local validation after the final v0.1.1 repair pass:
  - `.\build_exe.ps1` built `dist\ReplyRight\ReplyRight.exe`.
  - `dist\ReplyRight\ReplyRight.exe --health-smoke` exited successfully.
  - `.\installer\build_installer.ps1` built `installer\output\ReplyRightSetup-v0.1.1.exe`.
  - Full test suite passed with 445 tests, 1 existing warning, and 35 subtests.
- New release docs:
  - `docs/archive/migration/RELEASE_BLOCKERS_v0.1.0.md`
  - `docs/INSTALLER_STRATEGY.md`
  - `docs/archive/migration/NATIVE_UI_MIGRATION.md`
  - `docs/archive/migration/PYSIDE6_MIGRATION_PLAN.md`
- PySide6 shell files now exist in `replyright_qt/` and are launched by `run_desktop.py` after the FastAPI backend is healthy. Do not use `QWebEngineView`, Electron, Tauri, or any browser/WebView shell as the native UI.
- CI hardening pass completed after GitHub Actions failures on run #14:
  - `build_exe.ps1` now captures pip vendor-install output under non-terminating PowerShell error handling and checks the real native exit code, preventing successful pip installs with dependency-warning stderr from aborting clean CI builds.
  - `.github/workflows/build.yml` now gives pytest a 60-second per-test timeout to reduce Windows runner flakiness.
  - `outlook_dashboard/hotel_entities.py` bounds fuzzy date parsing on oversized inputs and skips expensive full-text `dateparser.search_dates()` calls when no date-like token exists.
- Documentation hardening pass completed: `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TRAINING_PIPELINE.md`, `docs/CLASSIFIER.md`, `docs/SECURITY_AND_PRIVACY.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS_GUIDE.md`, and `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` now describe the active FastAPI/pywebview app, inactive `app/` scaffold, experimental `replyright_kernel/`, training pipeline, local classifier, privacy boundaries, deployment workflow, and operator workflow.
- Phase 7 hotel domain intelligence layer is implemented and now used by `heuristic_analysis()` / `triage_email()` while keeping the modules themselves pure:
  - `outlook_dashboard/hotel_entities.py` exposes `extract_entities(subject, body, received_at=None)` for confirmation numbers, stay dates, nights, room category, rate code, guest counts, arrival window, and billing amounts.
  - `outlook_dashboard/travel_programs.py` exposes `detect_program(sender_email, body, signature=None)` for luxury travel program and advisor/agency detection.
  - `outlook_dashboard/urgency_engine.py` exposes `compute_urgency(...)` for arrival-window-aware urgency scoring from extracted entities and detected program metadata.
  - `dateparser` is now included in `requirements.txt`; the temporary `new_dependencies.txt` handoff file was removed during repository cleanup.
- Multilingual hotel workflow coverage now exercises Spanish, French, Portuguese, Italian, and German reservation patterns. Entity extraction recognizes localized confirmation/reservation, arrival/departure, night-count, guest-count, and presidential-suite terms; redaction recognizes localized confirmation-number labels; urgency scoring recognizes common localized billing, complaint, cancellation, thank-you, accessibility, allergy, and actionable-request terms.
- Previous onefile builds were rebuilt on 2026-05-18 with PyInstaller collection flags for scikit-learn/dateparser/joblib/threadpoolctl. Current source builds the onedir app at `dist\ReplyRight\ReplyRight.exe`.
- The UI has ReplyRight branding, provided logo/icon assets, an urgency-ranked conversation queue, summary/steps panels, local status changes, and an on-demand AI response modal.
- Outlook refresh is designed around classic Outlook for Windows and now uses read-only `pywin32` COM import as the primary path. The legacy `ExportNYCWAReservationsInboxOnly` VBA macro remains a fallback when direct import dependencies are unavailable.
- Refresh Inbox now attempts OpenAI classification when `OPENAI_API_KEY` is configured. The dashboard `OPENAI_MODEL` default is `gpt-5.4-nano`, selected after checking official OpenAI docs on 2026-05-17 for low-cost classification/extraction suitability. If OpenAI is not configured and `GOOGLE_AI_API_KEY` is present, Refresh Inbox attempts Google AI Studio/Gemini classification with structured JSON output. Local deterministic triage remains the fallback when external AI is unavailable or errors.
- Microsoft Graph OAuth code exists but is not the active path because the user hit enterprise access restrictions in Microsoft Entra.
- `build_exe.ps1` builds `dist\ReplyRight\ReplyRight.exe` as a PyInstaller onedir app and attempts Desktop/Start Menu shortcuts. The latest source uses the native PySide6 Qt shell, not WebView2/QWebEngine.
- A previous rebuilt onefile EXE was launch-tested by the user: the pywebview window opened, the dashboard loaded, and the sidebar tabs worked. The current onedir installer path still needs manual install validation.
- Refresh Inbox was verified through the packaged EXE: it directly read/imported 46 messages from `NYCWA_Reservations > Inbox`, analyzed 46 locally, skipped 0, and did not launch the VBA macro (`launch_method=pywin32-com`). A prior verification pass deleted 6 stale/non-current rows.
- The inbox API now returns 28 conversation groups from those 46 Outlook emails. Conversation details include the thread messages for the selected conversation.
- Owner routing is limited to operating departments: Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, and All Departments. There is no Management owner.
- Local triage classifies contact type as Internal, Group contact, Travel agency, or Direct guest.
- Queue urgency is now computed at the conversation level from the latest few messages, rather than taking the highest score from stale messages in the thread.
- Latest-message sentiment ignores quoted Outlook history where possible, so old upset text does not override a friendly/completed latest reply.
- Local adaptive feedback is implemented:
  - `triage_feedback` stores per-conversation correction notes plus optional corrected urgency, owner, category, contact type, sentiment, status, summary quality rating, and reply quality rating.
  - `POST /api/emails/{email_id}/feedback` applies feedback immediately to the selected conversation.
  - Similar future messages can reuse stored local feedback patterns.
- A CCA/completed-form pattern now routes to Reservations with concise steps to apply the form and confirm completion.
- Urgency is deliberately more conservative: level 5 is reserved for same/next-day operational blockers or serious risk, while completed/thank-you/form-submission updates are lowered unless a high-risk signal is present.
- `python -m pytest tests/ -x` passes with **424 tests** (35 subtests). One existing warning remains for `datetime.utcnow()` in auth reset-token code.
- Previous packaged health checks succeeded with 28 conversation groups and urgency distribution `2:14, 3:4, 4:7, 5:3`; current onedir builds should be validated through `--health-smoke` and the installer.
- `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` captures the broader Supabase/shared-learning roadmap.
- Confidence scoring (10–95%) is computed per email and shown as a color-coded pill in the UI.
- Rule candidate engine mines local feedback for recurring correction patterns. Three matching corrections create visible candidates; five or more mark the rule as auto-promoted for hands-off shared learning.
- Admin Suggested Rules now includes emergency `Reject` and `Dismiss` controls. Dismissed candidates are hidden locally; rejected candidates stay visible as rejected and are skipped by Supabase auto-promotion.
- Login uses Supabase Auth when configured and does not silently accept local SQLite passwords in that mode. Local SQLite users/sessions remain available only when Supabase is unconfigured. The configured Supabase admin account can still be repaired from `REPLYRIGHT_ADMIN_EMAIL` / `REPLYRIGHT_ADMIN_PASSWORD`; if no admin exists and Supabase service-role config is absent, first-run setup can create a local admin without asking for API keys.
- Login failures render a persistent static error message with an X close button and preserve the typed email address. Dashboard action failures such as invite/reset errors now use a persistent dismissable error toast.
- Auth middleware protects `/api/auth/me` and admin endpoints again. Public auth routes are limited to login/logout/forgot-password/reset-password, fixing the post-login dashboard boot loop.
- Admin view now has its own dashboard shell: the Refresh Inbox button is hidden while Admin is active, the topbar changes to Admin, and leaving Admin restores/rebinds the inbox queue/detail DOM so Inbox, Urgent, VIP, and Missing Info render correctly again.
- A previous packaged build after the admin navigation fix passed a headless Edge/Selenium Admin -> Inbox -> Urgent navigation check, including Refresh Inbox visibility.
- Roadmap audit completed and recorded in `docs/HANDOFF.md`. Phase 1 is mostly complete; the next blanks are structured feedback controls, Supabase durable sync/cache, hands-off rule auto-promotion, and a true staged AI pipeline.
- Brian answered the roadmap questions: summary quality and reply quality should be 1-5 ratings; shared learning rules should auto-promote hands-off with no required admin monitoring; multi-property/cross-property support is irrelevant and should be removed from the roadmap because ReplyRight is only for this hotel.
- Supabase approved rules are cached durably in local SQLite, and failed feedback uploads are queued locally for retry on the next configured startup.
- Supabase startup sync now also downloads and durably caches active prompt versions and known sender mappings. Known sender mappings are applied during local triage by sender domain for owner/contact-type corrections.
- A dedicated import smoke test now imports the active dashboard and Semantic Kernel modules so missing optional dependencies or broken import-time assumptions are caught earlier.
- Phase 7 of `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` now defines the long-term local hotel-specific training direction: import historical completed emails, redact/sanitize PII, AI-label sanitized examples, human-review samples, store a Supabase training dataset, train lightweight local classifiers, route by confidence, and use external AI only for low-confidence, complex, sensitive, summary, or reply-drafting work.
- Phase 7 should start with local classification targets only: urgency, owner, category, status, missing information, reply required, and escalation required. Do not try to train local polished reply writing first.
- **v0.1.0 optimization pass (2026-05-17):** All code optimizations applied — dead category-check branch removed from `ai.py`, bare JSON parse in `_analyze_with_claude` wrapped with proper error handling, SMTP code deduplicated in `auth.py`, three near-identical Supabase download functions unified in `supabase_client.py`, httpx.Client reused across `promote_rule_candidates` loop, `secrets` moved to top-level import in `main.py`, rate-limit bucket TTL pruning added, `registry.py` plugin loop introduced.
- **Phase 7 enterprise deployment (2026-05-17):**
  - **Supabase Auth migration**: All user authentication, session management, and admin provisioning now go through Supabase `/auth/v1/*` endpoints. No local SQLite user tables. Sessions stored as `access_token|||refresh_token` cookie (`rr_session`). Token refresh handled transparently in `_AuthMiddleware`.
  - **Runtime credentials**: provider and Supabase keys are not collected through the UI. They are supplied by ignored local `.env` files, machine environment variables, or GitHub Actions secrets during build/release workflows. `.env` takes precedence when present.
  - **Claude AI usage rule (CRITICAL)**: Claude/Anthropic is called ONLY when the user clicks the single-email "Analyze" button (`analyze_email()`). Bulk Refresh uses OpenAI → Google → heuristic only (no Claude). Violating this burns credits on every inbox refresh.
  - **EXE now includes anthropic**: `build_exe.ps1` uses `--collect-all anthropic` so the packaged EXE can call Claude without "No module named 'anthropic'" errors.
  - **Docker**: `Dockerfile` + `docker-compose.yml` for web-only server mode on Linux/Mac.
  - **Inno Setup installer**: `installer/replyright_setup.iss` builds a Windows installer wizard.
  - **Auto-updater**: `outlook_dashboard/updater.py` checks `ledostarmac2/hotel-email-triage` GitHub releases on startup.
  - **Platform compat**: `outlook_dashboard/platform_compat.py` provides `IS_WINDOWS`, `HAS_OUTLOOK_COM`, `HAS_WEBVIEW` flags for cross-platform safe guards.
  - **One-command setup**: `setup.ps1` installs Python, clones repo, creates venv, installs deps, builds EXE, and creates shortcuts. Run with: `irm https://raw.githubusercontent.com/ledostarmac2/hotel-email-triage/main/setup.ps1 | iex`
  - **GitHub Actions CI**: lint (syntax + pytest) on windows-latest + EXE build artifact + Docker health check on ubuntu-latest + release job triggered on `v*.*.*` tags that creates a GitHub Release with EXE attached.

## Known Local Build/Launch Notes

- Desktop launcher starts FastAPI, waits for `/healthz`, then opens the native **PySide6** shell. Do not reintroduce pywebview, QWebEngineView, Electron, Tauri, or another browser/WebView shell.
- `run_desktop.py` does a pre-flight `import clr` check and raises a descriptive error if pythonnet is missing, rather than crashing natively with no log entry.
- Startup logging is in `run_desktop.py`; packaged builds write to `dist\ReplyRight\data\replyright-startup.log`.
- `build_exe.ps1` auto-skips `.venv` and `.build-venv` to find system Python (VS Code auto-activates project venvs). If `.vendor` exists but is empty/partial, delete it and rebuild — the existence check short-circuits pip install.
- If Defender locks `dist\ReplyRight\ReplyRight.exe` or the onedir folder during a rebuild, the script falls back to renaming the old build out of the way. If both are locked, delete them manually first.
- Start Menu shortcut creation may fail on this locked-down Windows environment. Desktop shortcut creation uses the OneDrive Desktop path as a fallback.
- Local Python temp-directory permissions were unreliable. `build_support/sitecustomize.py` exists as a workaround for project-local dependency installation.
- Mock/demo data seeding has been removed from the active dashboard path.

## Config Requirements

Copy `.env.example` to `.env` for local runs. `.env` must not be committed. Release builds can receive credentials from GitHub Actions secrets or deployment-time files, and `.env` always takes precedence when present.

Important variables:

- `ANTHROPIC_API_KEY` — supplied by deployment config when enabled. Used ONLY for single-email Analyze button (Claude Opus).
- `ANTHROPIC_MODEL` — default `claude-opus-4-7`.
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — supplied by deployment config; all auth and data goes through Supabase when configured.
- `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` — Supabase Auth admin account credentials. `ensure_admin()` creates/repairs this user in Supabase on startup.
- `OPENAI_API_KEY` / `OPENAI_MODEL` — for Refresh Inbox bulk classification (not Analyze button).
- `GOOGLE_AI_API_KEY` / `GOOGLE_AI_MODEL` — fallback for Refresh Inbox when OpenAI not configured.
- `APP_HOST=127.0.0.1`, `APP_PORT=8000`
- `OUTLOOK_EXPORT_MAILBOX=NYCWA_Reservations`, `OUTLOOK_EXPORT_FOLDER=Inbox`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (for password reset emails).

**GitHub Actions Secrets** (set in repo Settings → Secrets → Actions):
- `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — used by CI to build the EXE and run the Docker health check.

**Supabase setup** (one-time): paste `docs/supabase_schema.sql` into the Supabase SQL Editor and run it. Creates `feedback_events`, `classification_rules`, `known_senders`, and `prompt_versions` tables with RLS policies.

## Current Risks

- The legacy VBA macro fallback must be installed manually only on machines where the direct `pywin32` import path is unavailable.
- The app must be running before Refresh Inbox; direct import happens in-process through the FastAPI endpoint.
- Outlook direct COM import depends on classic Outlook for Windows and bundled `pywin32`; if unavailable, ReplyRight falls back to the legacy `/autorun` VBA macro path.
- AI drafts are suggestions only and require human review.
- Supabase integration is wired: `upload_feedback_event()` fires after every correction and `download_approved_rules()` runs on startup. Uploads are a no-op until `SUPABASE_URL`/`SUPABASE_KEY` are set in `.env` and the schema is created (paste `docs/supabase_schema.sql` into the Supabase SQL Editor). **Both Supabase keys shared in session chat must be rotated before use.**
- The Google AI Studio key shared in session chat must also be rotated before use. Do not store pasted/shared keys in tracked files or docs.
- `.env` and `dist\ReplyRight\.env` may contain local admin/SMTP credentials and must not be committed or shared. The installer excludes `.env`.
- This app intentionally does not mutate Outlook messages; adding send/archive/move/category actions requires a new design and approval.
- Local mailbox exports and SQLite data are ignored for privacy and are not portable through git.
- Phase 7 training must remain privacy-preserving by default. Do not store raw hotel email bodies, guest PII, reservation numbers, payment details, or attachments in Supabase training tables unless Brian explicitly approves a new override.
- The hotel entity extractor depends on `dateparser`, which is now listed in `requirements.txt`.

## Semantic Kernel Orchestration Layer

A new `replyright_kernel/` Python package implements the foundational SK orchestration layer:

- **PriorityTriagePlugin** — local urgency scoring 1–5 (regex/keyword, no LLM cost)
- **ExecutiveSummaryPlugin** — strips HTML, quoted threads, signatures, legal footers, tracking noise; enforces 8 000-char token budget
- **AuditCompliancePlugin** — pre-display compliance scan; blocks guarantees, fault admissions, payment leakage, legal/medical/discrimination risk language, unapproved promises
- **engine.py / registry.py** — builds and registers the kernel; clearly labelled extension points for future Graph and CRM plugins
- **demo.py** — runnable four-step pipeline demo (`python -m replyright_kernel.demo`)

The layer is additive. It does not touch the existing FastAPI dashboard, Next.js scaffold, or Outlook read path.

Tests: `python -m unittest tests.test_kernel_plugins tests.test_kernel_orchestration` (59 tests, no API key required).

`OPENAI_MODEL` defaults to `gpt-5.5` in the kernel layer; the dashboard uses `gpt-5.4-nano` unless overridden. `KERNEL_LOG_LEVEL` controls kernel log verbosity.

## Recommended Next Steps

1. **Supabase schema**: if not yet run, paste `docs/supabase_schema.sql` into the Supabase SQL Editor (project `dxalumiijcfmwzmosijf`) and execute it once to create all tables.
2. **KYC Auto validation**: keep KYC Auto as a themed native PySide6 popup launched from the sidebar. It should run the bundled KYC browser automation from Start Timer or Run Now only; do not add due/history/snooze/skip/completed-by workflows back into the user-facing UI.
3. **KYC automation safety**: do not store KYC passwords in ReplyRight or run browser automation without an explicit user action.
4. **GitHub Secrets**: in the GitHub repo Settings → Secrets → Actions, confirm `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` are set so CI can build and test.
5. **v1 readiness plan**: use `docs/V1_RELEASE_PLAN.md` as the current gate list. The stale v0.1.1 emergency release checklist is historical; the next meaningful release work should align package, installer, diagnostics, beta evidence, training/classifier readiness, and safety UX.
6. **Local classifier training (Phase 7 long-term)**: import historical completed emails → redact PII → AI-label → human-review samples → store sanitized Supabase training set → train lightweight local classifiers. Start with urgency, owner, category, status, missing_information targets only.
7. **Refresh check**: click Refresh Inbox once and visually confirm the feedback box, resized window behavior, and Outlook-like independent scrolling.
8. **Login check**: confirm the app never prompts for API keys. On a fresh install with no admin, `/setup` creates the first admin through Supabase when service-role configuration exists and through local SQLite otherwise. Existing local database users should still be able to sign in. Bad credentials should show a persistent error with an X, good credentials should enter the app.
9. **Spot-check triage**: review conversations formerly over-scored as urgency 4/5, especially completed CCA/payment form threads and friendly travel-agent replies.
10. **If launch fails**: inspect `dist\ReplyRight\data\replyright-startup.log`. Look for `pythonnet (clr) is not available`; if seen, delete `.vendor` and re-run `.\build_exe.ps1` so pip re-installs pythonnet.
11. **Use the roadmap**: read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` before broad architecture work, especially Supabase shared learning and staged AI pipeline. Ignore multi-property/cross-property ideas unless Brian reopens them.
12. **Wire `replyright_kernel`** into `outlook_dashboard/ai.py` only where it supports the new split: OpenAI refresh classification, local fallback/tests, and Claude Opus `AI Suggestion`.
13. **Admin rules check**: after entering real feedback, confirm Suggested Rules shows Reject/Dismiss and that Dismiss removes a candidate from the local admin view.
14. **Phase 7 local learning**: when ready, implement incrementally in the documented order: Supabase training tables, sanitized training records, PII redaction, historical importer, AI batch labeler, human review queue, local classifier training, runtime prediction, admin controls, model activation/rollback, and metrics.
