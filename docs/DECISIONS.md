# Decisions

## 2026-05-19: Owner-Built Release Installer Includes Runtime Secrets

Decision: The GitHub Actions owner-built release installer should include the CI-provisioned runtime `.env` from repository Actions secrets so ReplyRight has OpenAI, Google AI, Claude, Supabase, admin seed, SMTP, and Microsoft configuration available immediately after install. CI must verify required runtime secrets are present without printing values.

Rationale: ReplyRight is being released for a controlled deployment where the owner expects the installer to be ready to run. Removing `.env` before installer creation left the released app without the API keys needed for AI and Supabase behavior.

## 2026-05-19: Hybrid Supabase And Local SQLite Auth

Decision: ReplyRight login should prefer Supabase Auth when configured, but must preserve local SQLite users and sessions as a fallback for existing installs and local-first/offline operation. First-run setup may create a local SQLite admin when no admin exists and Supabase service-role configuration is absent, without asking the user for API keys.

Rationale: The v0.1.1 Supabase-only migration broke installed database-backed credentials and fresh installs without bundled service-role credentials. Local auth fallback preserves the existing database contract and the local-first product requirement while still allowing Supabase Auth deployments.

## 2026-05-19: No In-App API Key Collection

Decision: ReplyRight must not display a credentials setup screen or ask end users for Supabase, OpenAI, Google, Anthropic, or other API keys inside the desktop app. Runtime credentials must come from deployment-time configuration, ignored local files, machine environment variables, or GitHub Actions secrets during release builds. The first-run setup surface is only for creating the first admin account, using Supabase when service-role configuration is present and local SQLite otherwise.

Rationale: Users should only sign in and operate the inbox. API-key handling is an owner/deployment concern, and exposing it in the installed app creates confusion and increases the chance that secrets are pasted into the wrong place.

## 2026-05-19: Native Qt Scaffold Remains Development-Only

Decision: The PySide6 scaffold may be launched only through an explicit development flag (`run_desktop.py --native` or `REPLYRIGHT_NATIVE=1`). Direct `replyright_qt/main_qt.py` execution stays guarded with `RuntimeError`, and the v0.1.1 production desktop path remains `run_desktop.py` starting FastAPI plus pywebview.

Rationale: The native UI work is useful migration scaffolding, but it is not production-wired or release-ready. The guard prevents accidental use while still allowing deliberate development experiments.

## 2026-05-18: Installer-First Releases And Health-Gated Desktop Startup

Decision: ReplyRight user releases must publish `ReplyRightSetup-v{version}.exe` as the primary release asset, with the raw PyInstaller `ReplyRight.exe` treated as an internal build input. The desktop launcher must start FastAPI, wait for `/healthz` to report healthy, and only then open the pywebview window. If startup fails, ReplyRight must show a controlled startup error instead of exposing a WebView or browser localhost connection error.

Rationale: The v0.1.0 GitHub release allowed a user-visible failure where the desktop window opened to `127.0.0.1 refused to connect`. That breaks the standalone desktop illusion and is not acceptable for a user release. Installer-first packaging also gives users shortcuts, uninstall behavior, WebView2 handling, and a more professional Windows installation path.

## 2026-05-18: Onedir Packaging And First-Run Admin Setup For v0.1.1

Decision: Build v0.1.1 as a PyInstaller onedir app at `dist\ReplyRight\ReplyRight.exe`, then package the full folder with Inno Setup while excluding local `.env`, runtime data, databases, and logs. Add a first-run setup route that creates the first admin when no admin exists, using Supabase when service-role configuration is available and local SQLite otherwise.

Rationale: Onedir packaging is easier to validate and install reliably than a single self-extracting EXE, and it lets the installer carry the full runtime bundle. First-run setup removes the requirement that a fresh user have a local `.env` admin seed before the first login.

## 2026-05-18: PySide6 Is The Recommended Native UI Migration Target

Decision: Keep pywebview only as a short-term bridge for v0.1.1 emergency repair. For v0.2.0, evaluate and prototype a PySide6 native desktop shell that reuses the existing Python intelligence, SQLite, Supabase, Outlook, classifier, and training modules through direct Python service calls. Do not use `QWebEngineView` as the main UI.

Rationale: pywebview still depends on a browser/WebView layer, so it can be patched but not made into the long-term zero-browser desktop experience Brian wants. PySide6 keeps the Python codebase and local-first model intact while removing localhost/WebView UI failure modes. WPF/WinUI remains a future option but carries higher interop and porting cost.

## 2026-05-17: Dashboard Refresh Uses GPT-5.4 Nano By Default

Decision: Refresh Inbox now attempts OpenAI classification when `OPENAI_API_KEY` is configured, with `OPENAI_MODEL` defaulting to `gpt-5.4-nano`. Local deterministic triage remains the fallback when OpenAI is unavailable or errors.

Rationale: Official OpenAI docs checked on 2026-05-17 describe GPT-5.4 nano as the cheapest GPT-5.4-class model and recommend it for speed/cost-sensitive classification and extraction. That fits ReplyRight's bulk refresh-classification workload better than using a larger drafting/reasoning model for every email.

## 2026-05-17: Google AI Studio As Optional Refresh Fallback

Decision: ReplyRight supports `GOOGLE_AI_API_KEY` / `GOOGLE_AI_MODEL` as an optional Google AI Studio/Gemini refresh-classification fallback when OpenAI is not configured. The integration uses Gemini REST structured output and stores keys only in local ignored environment files or machine environment variables.

Rationale: Brian has a Google AI Studio key available and wants the app prepared for it, but API secrets shared in chat must be treated as exposed. A local `.env` prompt script allows setup without printing or committing the key, and the app can still fall back to deterministic local triage if Google AI errors.

## 2026-05-17: Phase 2-4 Feedback And Rule Learning Slice

Decision: Structured feedback now captures corrected category, contact type, sentiment, status, and 1-5 summary/reply quality ratings in addition to urgency and owner. Rule candidates appear after three matching corrections, while five or more matching corrections are treated as auto-promoted.

Rationale: Brian requested 1-5 ratings and hands-off learning. The three-correction threshold provides visibility; the five-correction threshold gives stronger signal for automatic shared-rule promotion.

## 2026-05-17: Durable Supabase Learning Cache

Decision: Approved Supabase rules are cached locally in SQLite, and failed configured feedback uploads are stored in a local retry queue.

Rationale: Shared learning should remain useful when offline or when Supabase is temporarily unavailable. Feedback should not be lost just because a network call fails.

## 2026-05-17: Supabase Startup Metadata Sync

Decision: Startup sync now includes approved classification rules, active prompt versions, and known sender mappings. All three are cached in local SQLite, and known sender mappings are applied to local triage by sender domain.

Rationale: Shared learning needs more than classification rules. Prompt metadata and sender-domain knowledge should survive offline starts and should influence routine owner/contact-type classification without waiting for external AI.

## 2026-05-17: Admin Rule Emergency Overrides

Decision: Admin Suggested Rules includes emergency `Reject` and `Dismiss` actions. Dismiss hides a candidate locally; Reject keeps the candidate visible as rejected and skips Supabase auto-promotion.

Rationale: Brian wants hands-off rule promotion, but the system still needs a fast way to stop bad repeated-learning patterns without requiring routine approval for every good rule.

## 2026-05-17: Phase 7 Local Hotel-Specific Model Training Roadmap

Decision: Phase 7 should evolve ReplyRight toward a privacy-preserving local learning system that uses sanitized historical completed emails, AI-assisted labeling, human review sampling, Supabase training tables, lightweight local classifiers, confidence-based routing, and external AI fallback.

Rationale: Brian wants ReplyRight to become hotel-specific and reduce API usage over time. The practical path is not training a full LLM from scratch; it is training local classifiers for structured labels such as urgency, owner, category, status, missing information, reply required, and escalation required, while keeping OpenAI/Claude for low-confidence, complex, sensitive, summary, and reply-drafting work.

## 2026-05-17: Phase 7 Privacy-First Training Data

Decision: Phase 7 training data must be sanitized by default. Raw hotel email bodies, guest PII, reservation numbers, payment details, attachments, VIP identifiers, and similar sensitive content must not be stored in Supabase training tables unless Brian explicitly approves a future developer/admin override.

Rationale: Historical completed emails are valuable training data, but hotel email contains sensitive guest and operational information. ReplyRight should store operational patterns, hashes, metadata, sanitized text, labels, metrics, and feedback, not raw private guest records.

## 2026-05-16: OpenAI Refresh Classification, Claude Opus AI Suggestion

Decision: Refresh Inbox should use OpenAI to assign all triage metadata for imported emails, including urgency, owner, category, contact type, sentiment, missing information, executive summary, and required actions. Future implementation must check current official OpenAI model/pricing docs and choose the best available free-tier or lowest-cost suitable OpenAI model. Claude Opus is reserved for explicit `AI Suggestion` response drafting/refinement only.

Rationale: Brian wants refresh to classify the inbox automatically with AI, while reserving Claude Opus for the higher-value human-triggered response drafting experience.

## 2026-05-16: Hands-Off Shared Rule Auto-Promotion

Decision: Shared learning rules should auto-promote after repeated correction patterns. Admin UI should provide visibility and emergency override/rejection only; Brian should not need to monitor or approve routine learning.

Rationale: The strategic goal is a hands-off adaptive system where corrections improve future behavior automatically.

## 2026-05-16: Single-Hotel Scope

Decision: Remove multi-property and cross-property support from the active roadmap. ReplyRight is scoped to Waldorf Astoria New York / `NYCWA_Reservations`.

Rationale: Multi-property complexity is irrelevant for the user's current operational need and would distract from triage accuracy, feedback, and shared learning.

## 2026-05-16: 1-5 Quality Ratings

Decision: Summary quality and reply quality feedback should use 1-5 ratings.

Rationale: A 1-5 scale gives more useful learning signal than a binary thumbs up/down control.

## 2026-05-16: Current Runtime Is Python/FastAPI

Decision: Treat `outlook_dashboard/` and `run_desktop.py` as the active product path.

Rationale: It is the working dashboard and EXE path. The `app/` Next.js scaffold remains available for a future migration but is not the current app.

## 2026-05-16: Outlook Stays Read-Only

Decision: ReplyRight may read/import Outlook mail and update local review status only.

Rationale: Hotel reservations email is operationally sensitive. Sending, moving, deleting, marking read, or categorizing Outlook messages needs separate user approval and a safer workflow.

## 2026-05-16: Keep VBA Macro As Fallback Outlook Ingestion

Decision: Keep the classic Outlook VBA macro available as a fallback for `NYCWA_Reservations > Inbox` ingestion, but do not treat it as the primary path after the direct `pywin32` import was verified.

Rationale: The ChatGPT Outlook connector was blocked by enterprise policy, and Entra app registration access was unavailable. The macro path is still a useful escape hatch, but direct read-only COM import is more reliable on the current machine.

## 2026-05-16: Superseded - Local Rules For Bulk Triage, OpenAI On Demand

Decision: This was the earlier behavior: bulk refresh used deterministic local triage and OpenAI was reserved for explicit per-email response generation. This is superseded by the OpenAI Refresh Classification decision above.

Rationale: The old approach kept refresh fast and cheap during launch/debugging, but the target product now needs AI classification on refresh.

## 2026-05-16: SQLite Local Storage

Decision: Use local SQLite for messages, analysis, OAuth tokens, sync logs, and local statuses.

Rationale: It keeps the desktop app lightweight and avoids introducing a server database before the workflow is stable.

## 2026-05-16: Edge App Window Instead Of pywebview

Decision: The EXE starts FastAPI and opens Microsoft Edge in app mode.

Rationale: pywebview was unstable in the current Windows environment. Edge app mode gives a standalone-window feel with less native packaging risk.

## 2026-05-16: Switch Desktop Window From Edge App Mode To pywebview / WebView2

Decision: Replace the `msedge.exe --app` subprocess with `pywebview` using the `edgechromium` (WebView2) backend.

Rationale: Edge app mode opens through the user's existing Edge browser process, causing process-handoff (immediate exit, server shutdown) and no visual separation from the browser. pywebview with WebView2 creates a truly standalone embedded window — own taskbar entry, own process, no address bar, no tabs, no browser chrome. This is the same model VS Code uses (Electron/Chromium embedded). WebView2 Runtime is pre-installed on Windows 10 21H1+ and all Windows 11 machines.

## 2026-05-16: Outlook Refresh - Direct Read-Only COM Import

Decision: Make `pywin32` read-only Outlook COM import the primary Refresh Inbox path. ReplyRight connects to classic Outlook, reads only `NYCWA_Reservations > Inbox`, saves local `.msg` copies, normalizes messages in-process, and upserts them into SQLite. Keep `outlook.exe /autorun macroName` as a fallback only when `pywin32` is unavailable.

Rationale: Outlook's COM `Application` object on this machine does not expose `Run`, even through VBScript (`438 Object doesn't support this property or method`). Direct read-only COM avoids macro security prompts and the noisy PowerShell/CLIXML failure path while preserving the approved read/import-only Outlook posture.

## 2026-05-16: Outlook Refresh Is Local Source Of Truth

Decision: After a successful Outlook refresh, delete any local email row whose message id was not in the current Outlook import.

Rationale: The active dashboard should reflect the real shared Outlook inbox, not historical mock/demo rows or stale local imports. This deletes only ReplyRight's local SQLite copies and does not mutate Outlook.

## 2026-05-16: Conversation Groups Are The Inbox Unit

Decision: The inbox API groups email rows by Outlook `conversation_id` before rendering the queue. The selected conversation detail includes the thread messages for that conversation.

Rationale: Reservations work happens at the conversation/thread level. Grouping prevents duplicate queue rows and lets the user review the latest state of a thread in one place.

## 2026-05-16: Hotel-Specific Urgency And Routing

Decision: Urgency score is driven first by parsed arrival/check-in date: same day/next day = 5, same week = 4, same month = 3, later this year = 2, next year/future = 1. Upset guest or travel-agent sentiment can raise urgency. Department owners are limited to Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, and All Departments.

Rationale: Arrival date is the most operationally important signal for reservations triage, but sentiment still matters for recovery and service risk. Owner labels must match actual hotel operating departments.

## 2026-05-16: Conversation-Level Adaptive Feedback

Decision: Queue urgency and labels are computed at the conversation level from the latest few messages, with quoted Outlook history treated as context rather than the primary sentiment source. User feedback is stored locally in `triage_feedback` and can immediately override or guide urgency, owner, category, contact type, and sentiment.

Rationale: Reservations work is thread-based, and the latest reply often changes the required action. Local feedback gives the user short-term correction power now and creates a migration path for long-term shared learning.

## 2026-05-16: Supabase Shared-Learning Roadmap

Decision: Document Supabase as the target centralized learning repository in `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md`. GitHub remains for source, prompts, release notes, and approved config snapshots; Supabase is the future live feedback/rule database.

Rationale: Shared learning should improve all installations without storing raw email bodies, guest PII, reservation numbers, payment details, or attachments centrally.

## 2026-05-16: Local Admin Credentials Come From Environment

Decision: Configure the local ReplyRight admin account through `REPLYRIGHT_ADMIN_EMAIL` and `REPLYRIGHT_ADMIN_PASSWORD` in `.env`, and repair the existing admin hash on startup when the configured password changes.

Rationale: A hard-coded startup password can leave existing local databases with stale hashes and makes credential rotation awkward. Environment-backed credentials keep secrets out of source and make the packaged app repairable without deleting the SQLite database.

## 2026-05-16: Add Semantic Kernel Orchestration Layer As Additive Package

Decision: Implement the SK orchestration layer under `replyright_kernel/`, separate from `outlook_dashboard/`. The existing FastAPI dashboard is not modified.

Rationale: Keeps the proven dashboard stable while building the next-generation orchestration foundation alongside it. Future integration work (wiring SK into the `/api/emails/{id}/analyze` path) can be done incrementally and reviewed before replacing the current OpenAI call.

## 2026-05-16: Local Fallback Plugin Architecture For Token/Cost Control

Decision: PriorityTriage, ExecutiveSummary, and AuditCompliance remain useful as local fallback/test components. The target refresh path should use OpenAI staged classification, while Claude Opus remains reserved for explicit `AI Suggestion`.

Rationale: Local components keep tests deterministic and preserve offline fallback behavior, but they no longer define the primary refresh-classification strategy.

## 2026-05-16: Plugin Registry Extension Points Documented In Code

Decision: `registry.py` contains clearly labelled commented extension blocks for future Microsoft Graph Outlook plugins (Tier 2) and CRM lookup plugins (Tier 3).

Rationale: Future agents and engineers need to know exactly where to insert new plugins without reading the entire codebase. Comments in the registry serve as the canonical integration guide for the orchestration layer.

## 2026-05-16: Do Not Commit Runtime Artifacts

Decision: Ignore local data, exports, logs, build output, virtual environments, and vendored dependencies.

Rationale: These files are large, machine-specific, privacy-sensitive, or reproducible. Source, docs, config examples, assets, and build scripts should be committed.
