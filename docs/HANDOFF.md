# Handoff Log

## 2026-05-16 - Brian roadmap answers for tomorrow

Summary:

- Brian answered the open roadmap questions after the completion checklist.
- Feedback quality ratings should use a 1-5 scale.
- Shared learning rules should auto-promote. The system should be as hands-off as possible; Brian should not need to monitor rule approvals.
- Multi-property and cross-property support should be removed from the active roadmap. ReplyRight is for one hotel: Waldorf Astoria New York / `NYCWA_Reservations`.
- Refresh Inbox should use OpenAI to assign all triage metadata for imported emails: urgency, owner, category, contact type, sentiment, missing information, executive summary, and required actions.
- Future agents must check current official OpenAI model/pricing docs before choosing the refresh-classification model, then use the best available free-tier or lowest-cost suitable OpenAI model. Do not hard-code stale model assumptions.
- Claude Opus should only be used for explicit `AI Suggestion` response drafting/refinement, not bulk refresh classification.

Tomorrow's implementation direction:

1. Update feedback schema/UI/API for 1-5 summary quality and 1-5 reply quality ratings.
2. Add direct controls for corrected category, contact type, and sentiment.
3. Keep shared learning hands-off: rule candidates should auto-promote according to thresholds, with admin UI as visibility only.
4. Remove multi-property/cross-property roadmap items from active planning.
5. Start replacing local-only refresh triage with staged OpenAI refresh classification, while retaining local deterministic fallback and tests.

## 2026-05-16 - Roadmap completion checklist and next blanks

Summary:

- Completed a read-only audit of the current codebase against the seven-phase ReplyRight roadmap.
- No code changes were made for this audit.
- The active app is still `outlook_dashboard/` plus `run_desktop.py`; the Next.js scaffold remains historical.
- Tomorrow's first priority should be filling the roadmap blanks below, starting with structured feedback UI gaps, Supabase sync gaps, hands-off rule auto-promotion, and OpenAI refresh classification.

Roadmap checklist:

**Phase 1 - Core Functionality**

- [x] Outlook email ingestion from classic Outlook via read-only `pywin32` COM.
- [x] Local SQLite storage and source-of-truth refresh cleanup.
- [x] Conversation grouping.
- [x] Urgency classification.
- [x] Task owner assignment.
- [x] Executive summary / required-action summary.
- [x] Missing information detection.
- [x] Draft luxury-hospitality response generation.
- [~] OpenAI API analysis exists, but refresh classification still needs to be moved from local-only rules to OpenAI assignment of all triage metadata.
- [~] Staged AI pipeline is partly present through local rule stages; OpenAI/Claude analysis still uses one structured prompt.

**Phase 2 - Structured Feedback System**

- [x] Feedback box in email detail view.
- [x] Urgency correction.
- [x] Owner correction.
- [x] Status correction.
- [~] Category correction has backend/database support, but no direct UI control.
- [~] Contact type and sentiment correction have backend/inference support, but no direct UI controls.
- [ ] Summary quality rating using a 1-5 scale.
- [ ] Reply quality rating using a 1-5 scale.
- [ ] Direct edited-summary correction UI.
- [ ] Direct edited-reply feedback UI.

**Phase 3 - Supabase Integration**

- [x] Supabase schema exists.
- [x] Feedback event upload exists.
- [x] Approved classification rule download exists.
- [x] Downloaded rules are applied to local triage.
- [~] Rule cache exists in memory only, not durable offline cache.
- [~] Known sender table exists in schema, but sync/apply flow is not built yet.
- [ ] Prompt version download/sync.
- [ ] Supabase Auth.
- [ ] Durable offline queue for failed Supabase uploads.

**Phase 4 - Rule Candidate Engine**

- [x] One correction is stored locally for analytics.
- [x] Three similar corrections create local rule candidates.
- [x] Suggested rules appear in admin data.
- [~] Rule promotion exists and should remain hands-off/autopromoted; threshold behavior should be clarified in code.
- [ ] Five-plus correction threshold for stronger confidence/auto-promotion.
- [ ] Visibility-only admin lifecycle for promoted/rejected/dismissed rules, without requiring Brian to approve every rule.

**Phase 5 - Administrative Dashboard**

- [x] Admin tab exists.
- [x] Most corrected classifications.
- [x] Low-confidence analyses.
- [x] Suggested rules display.
- [x] User management / invites / reset links.
- [~] User adoption analytics has basic user count only.
- [~] Prompt performance has engine breakdown only, not prompt-version performance.
- [ ] Rule activity controls for visibility and emergency override only, not required approval.
- [ ] Rule rejection/dismiss controls for bad auto-promoted rules.
- [ ] Detailed urgency/owner misclassification drilldowns.

**Phase 6 - Enterprise Deployment**

- [x] Local authentication.
- [x] Admin/user roles.
- [x] Password reset/invite flow.
- [x] Runtime logging.
- [x] Read-only Outlook safety posture.
- [x] Payment-like data redaction before AI calls.
- [~] Security hardening has a local baseline, but no rate limiting, Supabase Auth, secret rotation workflow, or enterprise policy layer.
- [~] Monitoring is local rotating logs only.
- [ ] Centralized deployment/update strategy.
- [ ] Enterprise audit logs.
- [ ] Single-property permissions model for this hotel only.

**Phase 7 - Advanced Intelligence**

- [ ] Fine-tuned classification models.
- [ ] SLA tracking.
- [ ] Response-time analytics.
- [ ] Team productivity dashboards.
- [ ] Department-specific prompt/version management.

**Architecture / Stack Reality**

- [x] Active app is Python desktop-packaged app.
- [~] Desktop UI is FastAPI + pywebview/WebView2, not PySide6.
- [x] AI engine supports OpenAI API.
- [x] AI engine also supports Anthropic/Claude when configured.
- [x] Local cache/storage is SQLite.
- [x] Supabase shared learning is started but not complete.
- [x] GitHub/source-control structure exists.
- [x] VS Code/Codex handoff docs exist.

Recommended first work tomorrow:

1. Add direct UI controls for corrected category, contact type, and sentiment in the feedback box.
2. Add 1-5 summary quality and 1-5 reply quality ratings to local feedback and Supabase payloads.
3. Keep shared rule learning hands-off/autopromoted, with admin UI for visibility and emergency override only.
4. Add durable local cache/queue for Supabase rules, prompt versions, known senders, and failed feedback uploads.
5. Start splitting refresh classification into explicit OpenAI pipeline steps instead of one monolithic prompt; use Claude Opus only for `AI Suggestion`.

Roadmap questions answered by Brian:

- Feedback quality ratings should be 1-5.
- Shared rules should auto-promote; Brian does not want to monitor approvals.
- Multi-property support is irrelevant and should be removed from the active roadmap.
- OpenAI should classify/assign all triage fields during Refresh Inbox using the best current free-tier or lowest-cost suitable OpenAI model.
- Claude Opus should be used for `AI Suggestion` only.

## 2026-05-16 - Admin tab navigation restore

Summary:

- Fixed the Admin tab sticking bug. `renderAdminView()` had replaced the shared `.workspace` HTML, leaving the sidebar tabs rendering into detached inbox elements.
- Added a restorable inbox workspace shell in `app.js`; when leaving Admin, the queue/detail DOM is rebuilt, filter/search controls are re-cached and re-bound, and the selected view renders normally.
- Admin now updates the topbar to `Admin`, hides `Refresh Inbox`, hides the inbox metrics strip, and uses `.workspace--admin` instead of the CSS `:has()` selector.
- Rebuilt `dist\ReplyRight.exe` and refreshed Desktop/Start Menu shortcuts.

Files changed:

- `outlook_dashboard/static/app.js`
- `outlook_dashboard/static/styles.css`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/CHANGELOG_AI.md`

Verification:

- `python -m unittest tests.test_ai_and_database` - 10 tests OK
- `python -m py_compile outlook_dashboard\main.py outlook_dashboard\auth.py outlook_dashboard\database.py` - OK
- `.\build_exe.ps1` completed successfully and updated shortcuts.
- Headless Edge/Selenium source UI check passed: login -> Admin hides Refresh Inbox and shows Admin topbar; Admin -> Inbox restores `#emailList`, removes `.admin-shell`, and shows Refresh Inbox; Inbox -> Urgent remains on the inbox shell.

Remaining work:

- User should relaunch from the Desktop shortcut and manually confirm Admin -> Inbox/Urgent/VIP/Missing Info navigation in the packaged pywebview window.

## 2026-05-16 - Auth middleware skip-list fix

Summary:

- Root cause of the post-login flash/reset was `_AuthMiddleware` skipping every `/api/auth/*` route.
- Because `/api/auth/me` was skipped, `request.state.user` was never set; `api_me()` raised `AttributeError`, dashboard boot failed, and the UI bounced back to login.
- Narrowed the public auth skip list to only `/api/auth/login`, `/api/auth/logout`, `/api/auth/forgot-password`, and `/api/auth/reset-password`.
- Added a defensive 401 in `api_me()` if state is ever missing.
- Rebuilt `dist\ReplyRight.exe` and refreshed shortcuts.

Verification:

- `python -m py_compile outlook_dashboard\main.py outlook_dashboard\auth.py outlook_dashboard\config.py` - OK
- `python -m unittest tests.test_ai_and_database` - 10 tests OK
- Source auth check: anonymous `/api/auth/me` = 401; login = 303; authenticated `/api/auth/me` = 200.
- Packaged EXE auth check: anonymous `/api/auth/me` = 401; login = 303; authenticated `/api/auth/me` = 200 with user payload.

Remaining work:

- User should relaunch from the Desktop shortcut and try logging in again. This should no longer flash back to the blank login form.

## 2026-05-16 - Login error persistence and admin password repair

Summary:

- Moved local ReplyRight admin seeding to `.env` variables: `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD`.
- Changed `ensure_admin()` so startup repairs an existing admin account if the stored password hash does not match the configured local admin password.
- Updated `dist\.env` and root `.env` with the local admin and SMTP settings. Values are local secrets and must not be committed or pasted into docs.
- Changed failed form login behavior: invalid credentials now return the login page directly with HTTP 401, preserve the typed email address, and show a persistent static error message with an X close button.
- Changed dashboard error toasts for failed actions such as invite/reset/delete/startup failures so they persist until dismissed with X.
- Rebuilt `dist\ReplyRight.exe`; build copied `.env` to `dist\.env` and refreshed shortcuts.

Files changed:

- `.env.example`
- `outlook_dashboard/auth.py`
- `outlook_dashboard/config.py`
- `outlook_dashboard/main.py`
- `outlook_dashboard/static/login.html`
- `outlook_dashboard/static/app.js`
- `outlook_dashboard/static/styles.css`
- `tests/test_ai_and_database.py`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`

Verification:

- `python -m py_compile outlook_dashboard\auth.py outlook_dashboard\config.py outlook_dashboard\main.py` - OK
- `python -m unittest tests.test_ai_and_database` - 10 tests OK
- Focused FastAPI auth check - bad login returned 401 with persistent static error and preserved email; good login returned 303 with `rr_session` cookie.
- Packaged EXE auth check - health OK; bad login returned 401 with static error; good login returned 303 with session cookie.
- `.\build_exe.ps1` completed and updated Desktop/Start Menu shortcuts.

Remaining work:

- User should relaunch ReplyRight from the Desktop shortcut and log in again.
- If invite/reset emails still fail, the static error should remain visible; check whether O365 SMTP AUTH is disabled and consider Gmail app-password SMTP as noted previously.

## 2026-05-16 — Phase 5: Auth system, admin dashboard, invite flow, password recovery

### Summary

**Auth system (login gate)**
- New `outlook_dashboard/auth.py`: PBKDF2-HMAC-SHA256 password hashing (stdlib `hashlib`, no extra deps), session tokens (40-byte URL-safe, 30-day expiry), full user CRUD.
- New `users` and `sessions` tables in SQLite, added to `initialize_database()`.
- `_AuthMiddleware` added to FastAPI (before `_RequestLogMiddleware`): checks `rr_session` HttpOnly cookie on every request; skips `/login`, `/reset-password`, `/api/health`, `/static/`, `/api/auth/` prefix.
- `ensure_admin("brian.tarabocchia@waldorfastoria.com", "Luzmonkey63!", ...)` called in `lifespan()` — idempotent, only creates if absent. This password is ReplyRight-exclusive — not the Hilton/O365 login.
- **Login page**: two-panel layout (left: logo + brand, right: form). Form submits via server-side `POST /login` → `303 redirect /` with `Set-Cookie` header. This is more reliable in WebView2 than AJAX + `window.location.href`.
- **Silent login bug root cause & fix**: AJAX `fetch()` + `window.location.href = "/"` was unreliable in WebView2 (cookie not reliably carried through JS-triggered navigation). Fix: converted to real HTML form POST (`method="POST" action="/login"`). Server sets cookie on the redirect response directly.

**Admin dashboard**
- Nav: "Admin" button (purple, hidden) appears only for `role = "admin"`.
- `GET /api/admin/stats` returns: overview metrics (total emails, feedback, users, low-confidence count), engine breakdown, 30-day feedback trend, top corrections by category/owner/urgency, low-confidence emails, rule candidates.
- `renderAdminView()` in `app.js` renders a 4-metric overview strip, engine performance card, corrections table, low-confidence table, rule candidates table, and user management with invite form.

**Invite flow (email-only)**
- Admin enters the new user's email address only — no password field.
- `POST /api/auth/invite`: creates user account with a random placeholder password (user can never log in with it), generates a 24-hour reset token, sends an invite email via SMTP with a "Set My Password" link.
- Invited user clicks the link → `/reset-password?token=...` page → sets their own ReplyRight-exclusive password.
- Admin "reset password" button (🔑) in User Management now sends a reset link to the user's email instead of prompting the admin to type a new password.
- **Key design rule**: the admin never sees or sets another user's password. All credentials are user-controlled.

**Password recovery email**
- `POST /api/auth/forgot-password` (no auth required): generates 1-hour reset token, sends HTML email via SMTP.
- `GET /reset-password` serves `reset_password.html` (two-panel layout matching login page).
- `POST /api/auth/reset-password` (no auth required): consumes token (single-use), updates password hash.
- New `password_reset_tokens` table: `token`, `user_id`, `expires_at`, `used`, `created_at`.

**SMTP config**
- New fields in `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`.
- `smtp_configured` property: `bool(smtp_host and smtp_user and smtp_password)`.
- Defaults to `smtp.office365.com:587` (correct for Hilton/Waldorf O365).
- **Action required**: fill in `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` in `dist\.env` to enable invite + recovery emails. No rebuild needed — `.env` is read at runtime.

**AI suggestion fixes**
- `_salutation()`: removed "Mr./Ms." pattern entirely. Now: internal email → `Hi {first_name},`; external with name → `Dear {first_name},`; unknown → `Dear Guest,`.
- `heuristic_analysis()` model label: changed from `settings.openai_model` (leaked "gpt-4.1" even when heuristic ran) to `"local-rules"`.
- Claude is called only when "AI Suggestion" button is clicked — never on import or load.

**Adaptive feedback wiring**
- `_store_and_optionally_analyze()`: fetches `feedback_entries` once, passes to `triage_email(..., feedback_entries=...)`.
- `process_pending`: same — fetches and passes feedback entries so every import applies local correction history.

### Files changed

- `outlook_dashboard/auth.py` (new)
- `outlook_dashboard/static/login.html` (new two-panel layout + form POST)
- `outlook_dashboard/static/reset_password.html` (new)
- `outlook_dashboard/main.py` — auth middleware, login/reset/invite/forgot-password endpoints, admin stats endpoint, Form import
- `outlook_dashboard/database.py` — `users`, `sessions`, `password_reset_tokens` tables; `consume_reset_token()`; `admin_overview_stats()`, `admin_correction_stats()`, `admin_low_confidence_emails()`
- `outlook_dashboard/config.py` — SMTP fields added to `Settings`
- `outlook_dashboard/ai.py` — salutation fix, `heuristic_analysis()` model label fix
- `outlook_dashboard/static/app.js` — auth boot, logout, admin view, invite (email-only), reset-link flow
- `outlook_dashboard/static/styles.css` — logout btn, admin nav, admin layout cards
- `outlook_dashboard/static/index.html` — admin nav btn, user email display, logout btn
- `.env.example` — SMTP fields
- `dist\.env` — SMTP fields (credentials blank, to be filled)
- `build_exe.ps1` — auto-copies `.env` to `dist/` after each build

### Verification

- `dist\ReplyRight.exe` rebuilt successfully.
- Login form POST tested: server-side redirect with Set-Cookie.
- Admin account `brian.tarabocchia@waldorfastoria.com` / `Luzmonkey63!` auto-created on first launch.

### Action required before next session

1. **Fill in SMTP credentials in `dist\.env`** (no rebuild needed):
   ```
   SMTP_USER=brian.tarabocchia@waldorfastoria.com
   SMTP_PASSWORD=<your ReplyRight SMTP password>
   SMTP_FROM=brian.tarabocchia@waldorfastoria.com
   ```
   - If IT has SMTP AUTH disabled on your O365 account, use Gmail: `SMTP_HOST=smtp.gmail.com` + a [Gmail App Password](https://myaccount.google.com/apppasswords).
2. **Test invite flow**: go to Admin → User Management → enter a test email → "Send Invite" → confirm the email arrives with a "Set My Password" link.
3. **Test password recovery**: click "Forgot password?" on the login page → enter your email → confirm reset email arrives.

### Remaining work / known gaps

- The `POST /api/auth/users/{id}/reset-password` endpoint (admin sets password directly via API) still exists but is no longer used in the UI. Can be removed or kept for emergency admin use.
- No email enumeration protection on `forgot-password` (always returns `{"ok": true}` regardless of whether the email exists — this is correct behavior, no change needed).
- SMTP is synchronous (blocks the request thread). For large-scale use, move to a background task with `asyncio` or a queue. Fine for current single-team use.
- No rate limiting on auth endpoints. Fine for internal tool; add if exposed externally.
- Invite token uses the same `password_reset_tokens` table as forgot-password tokens (both are "set your password" flows, semantically equivalent).



## 2026-05-16 - Supabase integration, confidence scoring, rule candidate engine

Summary:

- **Confidence scoring**: `_confidence_for()` in `ai.py` scores each local triage 10–95% from three signals: category keyword strength, contact type clarity, urgency signal clarity. Stored in `email_analysis` and shown in the UI as a color-coded pill next to the urgency level (green ≥ 70, amber ≥ 40, red < 40).
- **Rule candidate engine**: `detect_rule_candidates()` in `database.py` mines `triage_feedback` for patterns: same sender domain → same owner correction (≥ 3 times), category repeatedly corrected to same value, urgency systematically shifted to same level. Surfaced via `GET /api/rule-candidates` and an amber dismissable banner in the UI (below the metrics strip) on app load when candidates exist.
- **Supabase shared-learning integration**:
  - `docs/supabase_schema.sql` created: paste into Supabase SQL Editor to create `feedback_events`, `classification_rules`, `known_senders` tables with RLS policies for the anon key.
  - `outlook_dashboard/supabase_client.py` created: httpx-based client, reads `SUPABASE_URL` / `SUPABASE_KEY` from env at call time. Silent no-op when unconfigured.
  - `upload_feedback_event()`: hashes sender_domain + subject_tokens (SHA-256) to produce a PII-free fingerprint, then uploads correction metadata to `feedback_events`. Called immediately after each `save_triage_feedback()`.
  - `download_approved_rules()`: GETs approved rows from `classification_rules` on startup (logged; future work is to apply them to the heuristic engine). Called in `lifespan()`.
  - `.env.example` updated with `SUPABASE_URL` / `SUPABASE_KEY` entries.
- **UI layout fixes** (from earlier in session): sidebar narrowed (200px), filter bar fixed to 3-column grid with full-width search, feedback controls stacked single-column, confidence badge styles, rule-candidates banner styles.
- **.msg cleanup**: stale `.msg` exports wiped at the start of each Refresh Inbox so the folder mirrors the current Outlook inbox exactly.
- Rebuilt `dist\ReplyRight.exe` (39 MB).

Files changed:

- `outlook_dashboard/supabase_client.py` (new)
- `docs/supabase_schema.sql` (new)
- `outlook_dashboard/ai.py`
- `outlook_dashboard/database.py`
- `outlook_dashboard/main.py`
- `outlook_dashboard/outlook_desktop.py`
- `outlook_dashboard/static/app.js`
- `outlook_dashboard/static/styles.css`
- `.env.example`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`

Verification:

- `python -m py_compile outlook_dashboard\supabase_client.py outlook_dashboard\main.py` - OK
- `.\build_exe.ps1` completed — `dist\ReplyRight.exe` 39 MB rebuilt.

Action required before Supabase uploads work:

1. **Rotate both Supabase keys** — they were shared in chat. Generate new ones in the Supabase dashboard → Project Settings → API.
2. **Paste `docs/supabase_schema.sql`** into the Supabase SQL Editor (project `dxalumiijcfmwzmosijf`) and run it once to create tables.
3. **Add to `.env`** (copy `.env.example`): `SUPABASE_URL=https://dxalumiijcfmwzmosijf.supabase.co` and `SUPABASE_KEY=<new publishable key>`.
4. Do NOT use the secret key (`sb_secret_...`) in the app — it bypasses RLS. Use it only in the Supabase dashboard/admin tools.

Remaining work:

- Apply downloaded Supabase rules to the heuristic classification engine (currently downloaded and logged but not yet used).
- Wire `known_senders` sync: upload corrected domain → owner mappings so they are shared across installs.
- Build the admin dashboard to review pending rule candidates and promote them to `classification_rules`.

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
