# ReplyRight Architecture And Vision Roadmap

Last updated: 2026-05-18

## 1. Product Vision

ReplyRight is a local-first desktop AI email triage assistant for luxury hotel operations.

The goal is not to replace human judgment. The goal is to help hotel teams process complex operational email faster, more consistently, and with better context. ReplyRight should classify incoming emails, identify urgency and ownership, summarize required action, surface risk flags, suggest luxury-appropriate replies, and learn from human corrections over time.

The long-term vision is a hotel-trained operational intelligence layer that can run locally, reduce API dependency, protect sensitive guest information, and adapt to Waldorf Astoria New York reservation workflows.

ReplyRight should remain:

- Local-first where practical
- Human-supervised
- Explainable
- Cost-conscious
- Privacy-conscious
- Designed for luxury hotel service standards
- Built around real hotel operations, not generic inbox productivity

## 2. Current Project State

The active runnable app is:

```text
outlook_dashboard/
run_desktop.py
```

The current desktop architecture is:

```text
PyInstaller Windows EXE
  -> run_desktop.py
  -> FastAPI server in outlook_dashboard/main.py
  -> pywebview / WebView2 desktop shell
  -> http://127.0.0.1:8000 UI
  -> SQLite + Supabase + Outlook COM/Graph + optional AI APIs
```

The inactive scaffold is:

```text
app/
```

It is an unused Next.js scaffold and should not be treated as the active application unless a future migration is explicitly planned.

The experimental Semantic Kernel layer is:

```text
replyright_kernel/
```

It is additive and not currently wired into the runnable desktop app.

Current core modules include `main.py`, `ai.py`, `database.py`, `graph.py`, `outlook_desktop.py`, `auth.py`, `taxonomy.py`, `taxonomy_meta.py`, `signal_extractor.py`, `sender_intelligence.py`, `local_classifier.py`, `hotel_entities.py`, `travel_programs.py`, `urgency_engine.py`, `training_pipeline.py`, `redaction.py`, `supabase_client.py`, `updater.py`, and supporting utility modules.

The current system includes deterministic signal extraction, hotel entity extraction, travel-program detection, deterministic urgency scoring, local classification, sender intelligence, Supabase-approved rules, optional AI fallback, admin dashboards, training workflows, Supabase Auth, audit logging, versioning, auto-update support, and a passing automated test suite.

The Phase 7 hotel entity, travel program, and urgency modules are implemented and tested, but intentionally not wired into `triage_email()` yet.

## 3. Architectural Principles

### 3.1 Do Not Turn ReplyRight Into One Giant Prompt

ReplyRight should use layered intelligence:

1. Deterministic extraction
2. Rules and taxonomy metadata
3. Local model prediction
4. Sender reputation
5. Shared approved rules
6. Optional external AI summary and reply generation
7. Human correction and feedback loop

External AI should enhance the system, not become the only intelligence layer.

### 3.2 Local-First Is A Strategic Advantage

The local classifier, SQLite model storage, Outlook COM support, deterministic heuristics, and packaged Windows EXE are core advantages.

The app should remain useful even when:

- No OpenAI key is present
- No Claude key is present
- No Google AI key is present
- Supabase is temporarily unreachable
- The user wants to avoid per-email API costs
- The hotel wants tighter control over sensitive guest information

### 3.3 Human Approval Must Stay Central

ReplyRight should assist with classification, triage, drafting, routing, and decision support.

It should not silently send replies, alter reservations, modify billing, or make final service-recovery decisions without explicit human approval.

### 3.4 Every Decision Should Be Explainable

For each analyzed email, the app should be able to explain:

- Why the urgency was selected
- Why the owner was selected
- Why the category was selected
- Which risk flags were detected
- Which signals and entities were extracted
- Whether the result came from heuristics, local classifier, shared rules, sender intelligence, external AI, or human correction
- What the confidence level was
- Whether human review is required

### 3.5 Hotel Operations Are Risk-Sensitive

The app must treat the following as high-risk domains:

- Billing disputes
- Refund requests
- Credit card authorization
- ADA/accessibility
- Medical issues
- Legal threats
- VIP/consortia bookings
- Same-day arrival issues
- Group blocks
- Guest recovery
- Social/review escalation
- Security or safety language

These must be surfaced clearly and conservatively.

## 4. Current Intelligence Pipeline

The current and intended email analysis flow is:

```text
Incoming email
  -> latest-message cleanup and redaction where needed
  -> local classifier prediction when a trained model is available
  -> deterministic hotel triage fallback
  -> shared Supabase rules and known sender mappings
  -> optional OpenAI refresh classification
  -> optional Google AI refresh fallback
  -> local SQLite storage
  -> dashboard summary, category, urgency, owner, risk, next steps
  -> user feedback
  -> Supabase feedback and training pipeline
```

Planned enrichment after the parallel Phase 7 merge:

```text
extract_signals()
  -> extract_entities()
  -> detect_program()
  -> compute_urgency()
  -> get_effective_sla_hours()
  -> local_classifier.predict()
  -> apply sender intelligence and shared rules
  -> optional external AI fallback
```

### Signal Extraction

`signal_extractor.py` extracts zero-API hotel signals including tone, VIP language, billing language, complaint language, urgency terms, group inquiry patterns, dollar amounts, sender identity, follow-up status, temporal language, and structure.

### Entity Extraction

`hotel_entities.py` extracts confirmation numbers, stay dates, nights, room categories, rate codes, guest counts, arrival windows, and billing amounts. It includes multilingual hotel workflow coverage and remains pure Python.

### Travel Program Detection

`travel_programs.py` detects luxury and VIP travel programs such as Virtuoso, FHR, STARS, Signature, Mr_and_Mrs_Smith, Impresario, Hyatt Prive, FS Preferred, and internal Hilton communications.

### Urgency Engine

`urgency_engine.py` computes deterministic arrival-window-aware urgency from extracted entities, detected program metadata, risk language, billing/complaint/accessibility cues, cancellation timing, acknowledgments, and actionable request language.

### Taxonomy Metadata

`taxonomy.py` defines active category, owner, risk, status, and contact-type values. `taxonomy_meta.py` defines SLA timing, colors, escalation paths, risk overrides, owner descriptions, contact-type multipliers, and helper functions.

### Local Classifier

`local_classifier.py` trains TF-IDF plus calibrated LogisticRegression models from human-reviewed Supabase `training_examples`. Current targets are urgency, owner, and category. Models are persisted in local SQLite with metadata, previous-version retention, cross-validation accuracy, label distribution, feature importance, and per-class confidence thresholds.

### Sender Intelligence

`sender_intelligence.py` builds per-domain profiles from Supabase feedback events. It should remain a nudge layer unless profile confidence is very high.

### Shared Rules

Supabase-approved rules sit above local prediction as explicit business logic. Rules should be reviewable, auditable, reversible, and cached locally for offline use.

### Optional AI Fallback

OpenAI and Google AI support refresh classification. Claude is reserved for explicit single-email analysis/drafting and admin-explicit training refinement. External AI is not required for baseline classification.

## 5. Roadmap By Phase

### Phase 0: Stabilize The Current Build

Goal: keep the packaged EXE aligned with the current intelligence layer.

Status on 2026-05-18:

- `dist\ReplyRight.exe` was rebuilt with PyInstaller collection flags for scikit-learn, dateparser, joblib, and threadpoolctl.
- Packaged `/api/health` returned `ok=true`.
- Packaged SQLite contains `training_pipeline_log`.
- The training pipeline endpoint executed successfully.
- Supabase `training_examples` returned rows through a service-role REST check.
- `docs/supabase_schema.sql` includes the `label_contact_type` migration.

Remaining:

- Merge `dateparser` from `new_dependencies.txt` into the active dependency file after the parallel branch is reconciled.
- Re-run classifier training after enough reviewed examples exist.
- Keep smoke-testing each rebuilt EXE.

Definition of done: migration applied, label import/training pipeline healthy, classifier retrained when sufficient reviewed data exists, EXE rebuilt, app launches, dashboard loads, Refresh Inbox works, admin classifier health works, and tests pass.

### Phase 1: Documentation Hardening

Goal: make the project understandable to future Codex sessions and developers without relying on chat history.

Required docs:

- `README.md`
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/TRAINING_PIPELINE.md`
- `docs/CLASSIFIER.md`
- `docs/SECURITY_AND_PRIVACY.md`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS_GUIDE.md`
- `docs/TESTING.md`

Definition of done: current active app, inactive scaffold, experimental kernel, training flow, classifier flow, privacy posture, deployment, and operator workflows are documented.

### Phase 2: Confidence, Review, And Safety UX

Goal: make the UI safer and clearer for real hotel users.

Tasks:

- Show separate confidence indicators for classification, entities, SLA, risk detection, and reply quality.
- Add a clear Needs Human Review state for low confidence, billing disputes, legal language, ADA/accessibility, medical issues, VIP with low confidence, same-day arrivals, and serious complaints.
- Add explanation surfaces for signals, entities, risk flags, SLA, owner, escalation, and classification source.
- Improve Signal Inspector for non-technical admin users.
- Keep explicit warnings on AI-generated replies.

Definition of done: users can see why a result was produced, low-confidence work is clearly separated, and risky emails are not buried.

### Phase 3: Real-World Internal Beta

Goal: test ReplyRight against live hotel inbox behavior with limited users.

Scope:

- Brian only at first
- Optional one trusted colleague later
- Read-only mode
- Copy-paste reply drafts only
- No send button
- No automated mailbox modification

Track weekly:

- Total emails analyzed
- High-confidence percentage
- Low-confidence queue percentage
- Urgency, owner, category, and risk correction rates
- Suggested reply usability
- Average time saved
- Top recurring failure patterns and sender domains

Definition of done: 500 to 1,000 real emails reviewed, correction stats available, failure categories documented, classifier retrained on real corrections, and no major privacy or packaging issues.

### Phase 4: Training Loop Expansion

Goal: make ReplyRight progressively better from user feedback.

Tasks:

- Capture original and corrected category, urgency, owner, contact type, risk flags, summary quality, reply quality, and correction notes.
- Add correction reason codes.
- Add feedback quality states such as raw feedback, reviewed feedback, training ready, and excluded.
- Feed feedback into sender intelligence, local classifier retraining, suggested rules, prompt evaluation, and confidence tuning.
- Add training set health checks for minimum examples, class imbalance, label conflicts, stale models, and high correction rates.
- Add deliberate candidate model training, comparison, promotion, and rollback.

Definition of done: feedback can become training data safely, retraining is measurable, bad feedback can be excluded, and model promotion is not automatic.

### Phase 5: Reply Draft Quality System

Goal: improve suggested replies while preserving human control and hotel brand standards.

Tasks:

- Create tone profiles for luxury guest-facing, internal operations, travel advisor, billing resolution, service recovery, concierge, executive VIP, acknowledgment, and policy clarification.
- Route prompts by category and contact type.
- Add prompt versioning and performance tracking.
- Capture reply feedback: copied as-is, copied with edits, rejected, regenerated, tone issues, length issues, policy issue, missing detail.
- Warn on risky reply promises around refunds, compensation, legal statements, ADA commitments, billing promises, guaranteed upgrades, early check-in, late checkout, or rate exceptions.

Definition of done: replies are routed by use case, drafts are auditable, risky promises are flagged, and prompt performance can be measured.

### Phase 6: Operational Workflow Features

Goal: move from classification to practical hotel task support.

Tasks:

- Add action recommendations such as reply to guest, loop in Reservations, loop in Front Office, loop in Concierge, escalate, check reservation, verify payment authorization, review folio, request missing information, or no action required.
- Add owner-specific task summaries.
- Add SLA countdowns based on category, urgency, contact type, risk flags, and arrival window.
- Add queue views for Immediate, Today, Waiting on Guest, Waiting on Internal Team, Billing Risk, VIP/Travel Advisor, Complaints, Low Confidence, and No Action Likely.
- Add duplicate/follow-up threading based on sender, subject, confirmation number, guest name, and repeated follow-up language.

Definition of done: users can work from ReplyRight as a triage dashboard, emails are grouped by operational need, SLA risk is visible, and suggested next action is practical.

### Phase 7: Local Model Maturity And Reduced API Dependency

Goal: train ReplyRight to classify hotel emails well enough that API calls are optional rather than required.

Strategy: use external AI to create or refine high-quality labeled data, not as the permanent classification engine.

Short-term targets:

- Strong urgency classification
- Strong owner classification
- Solid category classification
- Reliable risk support via deterministic extraction

Medium-term targets:

- Contact type classification
- Reply tone routing
- Duplicate/follow-up detection
- No-action detection
- SLA-risk prediction

Long-term targets:

- Retrieval from similar sanitized historical examples
- Per-property model variants only if Brian reopens multi-property needs
- Optional local LLM support only after classification is stable

Definition of done: routine triage is mostly local, API calls are reduced, accuracy improves with feedback, classifier health is visible, and training is repeatable.

### Phase 8: Security, Privacy, And Compliance Hardening

Goal: prepare the app for serious workplace use.

Tasks:

- Confirm no raw email bodies, guest names, email addresses, phone numbers, credit card data, confirmation numbers, or full messages appear in logs.
- Improve PII redaction coverage.
- Add privacy modes for external AI usage.
- Add roles such as viewer, agent, supervisor, admin, and developer.
- Restrict admin tools: classifier training, rule approval, user management, audit log, prompt activation, sender intelligence lookup, model rollback, and update installation.
- Add audit records for corrections, rule approval, model training, model promotion, prompt changes, user invite/reset, app update, and external AI usage.
- Document data flow from Outlook to local app, SQLite, Supabase, optional external AI, and GitHub releases.

Definition of done: sensitive data flow is documented, risky admin actions are audited, external AI behavior is configurable, and outbound action still requires human approval.

### Phase 9: Deployment And Update System

Goal: make the app easy to install, update, and support.

Tasks:

- Harden PyInstaller build and hidden imports.
- Add build validation and post-build smoke tests.
- Improve update card, release notes, and rollback instructions.
- Add diagnostics showing app version, commit hash, build date, Python version, Windows version, database path, SQLite status, Supabase status, Outlook Graph status, Outlook COM status, AI provider status, classifier version, last sync, and last training time.

Definition of done: a colleague can install the EXE, updates are visible, support issues can be diagnosed, and the build process is repeatable.

### Phase 10: Optional Controlled Reply Sending

Do not implement until internal beta is successful, classification confidence is strong, reply drafts are consistently usable, audit system is mature, role permissions are working, and legal/privacy concerns are reviewed.

Required future sending flow:

1. User opens draft.
2. User reviews full original email.
3. User reviews generated reply.
4. User edits or approves reply.
5. App shows risk warnings.
6. User confirms final send.
7. App stores an audit record.
8. App sends through an approved mailbox integration.

Definition of done: no silent sending, no automatic replies, explicit human approval, and auditable sent replies.

### Phase 11: Semantic Kernel / Agent Layer

Goal: use `replyright_kernel/` only if it adds clear value.

Potential use cases:

- Multi-step triage workflows
- Plugin-based hotel operations reasoning
- Structured escalation workflows
- Complex inbox batch processing
- Policy-aware task planning

Do not use it for basic classification, simple summaries, or anything already handled by deterministic modules.

Definition of done: the kernel layer has one clearly useful workflow, is tested, remains optional, and does not destabilize the desktop app.

### Phase 12: Single-Property Maturity

Goal: mature ReplyRight for the Waldorf Astoria New York workflow before considering broader enterprise features.

Brian has said multi-property/cross-property support is irrelevant for now. Keep the roadmap focused on the current property unless that direction is explicitly reopened.

Future single-property configuration should cover:

- Property name and timezone
- Room types
- VIP programs
- Owners
- Escalation contacts
- SLA rules
- Signature templates
- Policy snippets

Definition of done: one codebase supports this property reliably, without introducing unnecessary enterprise complexity.

## 6. Current Ship Readiness Assessment

ReplyRight is best described as:

```text
Late-stage internal alpha / early beta
```

It is not just a prototype. It is not yet ready for broad colleague rollout.

Primary blockers:

- Real-world beta metrics are not yet collected.
- Confidence and safety UX need hardening.
- Training examples need enough human review to train a durable classifier.
- Documentation must stay current as the Phase 7 branches merge.
- Reply sending remains out of scope.

## 7. Readiness Gates

### Gate A: Developer-Ready

- Docs are current.
- Tests pass.
- Build instructions work.
- Active vs inactive folders are clear.
- Codex can safely modify the repo using `AGENTS.md`.

### Gate B: Personal Daily-Use Ready

- EXE runs reliably.
- Email sync works.
- Analysis works.
- Corrections are captured.
- Classifier can be retrained.
- Low-confidence queue works.
- No data/logging issues are found.

### Gate C: Trusted-Colleague Beta Ready

- Install/update process works.
- User management works.
- Confidence indicators are clear.
- Human review queue is clear.
- Audit log works.
- Documentation exists.
- Known failure cases are documented.

### Gate D: Department Rollout Ready

- At least 1,000 real emails reviewed.
- Correction rates are acceptable.
- Risk flag misses are rare and monitored.
- Training loop is stable.
- Admin workflows are stable.
- Privacy settings are clear.
- Support diagnostics exist.
- Reply sending is still disabled or strictly approval-gated.

## 8. Non-Goals For Now

Do not prioritize:

- Full Next.js migration
- Mobile companion
- Automatic reply sending
- Multi-property support
- Deep Semantic Kernel workflows
- Full analytics suite
- Complex enterprise permissions
- Calendar integration
- Automatic reservation modification
- Fully autonomous guest communication

## 9. Codex Implementation Rules

When modifying this project:

1. Treat `outlook_dashboard/` as the source of truth.
2. Do not move active logic into `app/` unless explicitly requested.
3. Preserve local-first operation.
4. Do not require paid AI APIs for baseline classification.
5. Do not log raw email bodies.
6. Do not weaken PII redaction.
7. Do not add automatic sending.
8. Do not remove human approval gates.
9. Keep deterministic logic separate from AI-generated reasoning.
10. Keep taxonomy metadata centralized.
11. Add or update tests for meaningful behavior changes.
12. Update documentation whenever architecture changes.
13. Prefer small, reviewable changes.
14. Preserve Windows/PyInstaller compatibility.
15. Preserve read-only Outlook behavior unless explicitly instructed otherwise.
