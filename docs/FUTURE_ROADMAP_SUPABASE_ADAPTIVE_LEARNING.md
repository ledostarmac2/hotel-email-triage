# ReplyRight Future Roadmap: Supabase Adaptive Learning

> **Status as of v0.1.0 (2026-05-18):** Phases 1-6 are complete and committed. Phase 7 is partially implemented: the training pipeline, Supabase `training_examples`, local scikit-learn classifier, hotel entity extraction, travel program detection, and deterministic urgency engine exist. Historical import, richer review workflows, model comparison/promotion, and full runtime wiring remain future work. Current source verification: 424 automated tests plus 35 subtests pass.

## Project Vision

ReplyRight is an enterprise-grade AI assistant for Outlook that helps the Waldorf Astoria New York reservations and operations teams triage and respond to email more efficiently.

The application performs four core functions:

1. Prioritizes emails by urgency.
2. Determines which department owns the task.
3. Summarizes exactly what action is required.
4. Drafts a brand-appropriate AI response.

The long-term goal is a feedback-driven shared intelligence platform where corrections made by any user improve performance for all users automatically, without requiring Brian to manually approve routine learning rules.

## Core Problem To Solve

The current application works, but AI accuracy is inconsistent in these areas:

- Determining urgency levels.
- Identifying task ownership.
- Summarizing actionable next steps.
- Detecting missing information.
- Producing consistently accurate replies.

If every installation learns independently, each user must retrain the system manually. The objective is centralized learning so all feedback is shared across the organization.

## Strategic Architecture

```text
ReplyRight Desktop Application
    -> Local Cache (offline support)
    -> Supabase (central shared learning database)
    -> Rule Engine + Metadata Repository
    -> OpenAI API
    -> Improved classifications for all users
```

Optional supporting layer:

```text
GitHub Repository
    -> Version-controlled prompts and configuration backups
```

## Technology Stack

| Component | Platform |
| --- | --- |
| Desktop application | Python + FastAPI backend + native PySide6 shell |
| AI engine | OpenAI API |
| Central database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth |
| Local cache | JSON / SQLite |
| Version control | GitHub |
| IDE | VS Code |
| Primary coding agent | Codex |

Note: the current desktop direction is FastAPI for the local backend plus a native PySide6 shell. Do not reintroduce pywebview, `QWebEngineView`, Electron, Tauri, or another browser/WebView shell.

## Why Supabase

Supabase provides:

- Hosted PostgreSQL database.
- Built-in REST APIs.
- Authentication.
- Row Level Security.
- File storage.
- SQL editor.
- Analytics.
- Scalability.

Supabase should serve as the centralized knowledge and feedback repository.

## Role Of GitHub

GitHub should not be used as a live database.

GitHub is best for:

- Source code.
- Prompt templates.
- Approved configuration snapshots.
- JSON rule exports.
- Release notes.

Supabase is used for live operational data.

## Shared Learning Concept

Every user can correct:

- Urgency.
- Owner.
- Category.
- Status.
- Summary quality.
- Reply quality.

Summary quality and reply quality should be captured as 1-5 ratings. These corrections are uploaded to Supabase. The system analyzes repeated correction patterns and auto-promotes rules hands-off. Admin views are for visibility and emergency overrides, not routine approval.

## Database Tables

Planned Supabase tables:

- `users`
- `feedback_events`
- `classification_rules`
- `prompt_versions`
- `known_senders`
- `owner_mappings`
- `urgency_rules`
- `rule_candidates`
- `audit_logs`

Example `feedback_events` payload:

```json
{
  "email_fingerprint": "hashed_value",
  "sender_domain": "alchemyconcierge.com",
  "original_ai_urgency": 5,
  "corrected_urgency": 3,
  "original_owner": "Concierge",
  "corrected_owner": "Reservations",
  "original_category": "VIP pre-arrival",
  "corrected_category": "Travel agency confirmation",
  "confidence": 0.72,
  "prompt_version": "v1.4",
  "app_version": "0.8.2",
  "timestamp": "2026-05-16T12:30:00",
  "summary_quality_rating": 5,
  "reply_quality_rating": 4,
  "notes": "Already completed. No reply required."
}
```

## Privacy And Security

Do not store centrally:

- Raw email bodies.
- Guest names.
- Reservation numbers.
- Payment details.
- Attachments.
- Credit card information.

Instead store:

- Hashed email fingerprints.
- Sender domains.
- Classification metadata.
- User corrections.
- Prompt and app version metadata.

## AI Pipeline

Refresh Inbox should use OpenAI to assign all triage metadata for imported emails. Before implementation, check current official OpenAI model/pricing docs and choose the best available free-tier or lowest-cost suitable OpenAI model. Claude Opus should be reserved for explicit `AI Suggestion` drafting/refinement and should not be used for bulk refresh.

The application should not ask AI to perform all reasoning in a single prompt. Use a staged pipeline:

1. Extract facts.
2. Detect sender type.
3. Detect guest, stay, VIP, and payment signals.
4. Determine required action.
5. Assign task owner.
6. Score urgency.
7. Identify missing information.
8. Generate executive summary.
9. Draft reply.

This improves consistency, testability, and debugging.

## Rule Engine

Rules should handle predictable scenarios before invoking AI.

Example:

If sender is a travel agency and the email references confirmation, rates, commission, VIP, or amenities, assign Reservations as owner unless operational delivery is required.

Urgency examples:

Level 5:

- Arrival within 24 hours.
- Guest currently in house.
- Payment issue blocking stay.
- Accessibility issue.
- Leadership copied.
- High-profile VIP.

Level 1:

- Thank-you email.
- Completed chain.
- FYI only.
- Marketing content.

## Confidence Scoring

Every classification should include:

- Score from 0 to 100%.
- Reasoning summary.

Example:

```text
Urgency: 5
Confidence: 72%
Reason: Arrival tomorrow and VIP pre-arrival request.
```

Low-confidence outputs should be marked for human review.

## Feedback Logic

- 1 correction: store for analytics.
- 3 similar corrections: generate rule candidate.
- 5+ similar corrections: auto-promote with stronger confidence and keep an admin-visible audit trail.

## Admin Dashboard

The system should include an administrative interface displaying:

- Most corrected classifications.
- Urgency misclassifications.
- Owner misclassifications.
- Low-confidence emails.
- Suggested and auto-promoted rules.
- Prompt version performance.
- User adoption metrics.

Admin review should not be required for routine learning. The dashboard should provide visibility, diagnostics, and emergency override/reject controls.

## Startup Synchronization

On application launch:

1. Authenticate with Supabase.
2. Download latest approved rules.
3. Download prompt templates.
4. Download known sender mappings.
5. Cache all data locally.
6. Begin email analysis.

If offline, use cached configuration.

## Local Caching

Use local JSON or SQLite for:

- Rules.
- Prompts.
- Sender mappings.
- Recent feedback queue.
- Offline operation.

## Suggested Future Directory Structure

```text
replyright/
├── app/
├── ai/
├── feedback/
├── rules/
├── supabase/
├── cache/
├── admin/
├── prompts/
├── docs/
│   └── FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md
└── tests/
```

## Development Phases

Phase 1 - Core Functionality:

- Email ingestion.
- Summaries.
- Urgency classification.
- Ownership assignment.
- Reply generation.

Phase 2 - Structured Feedback:

- Correction controls.
- Local feedback capture.

Phase 3 - Supabase Integration:

- Centralized feedback database.
- Shared metadata download.

Phase 4 - Rule Candidate Engine:

- Pattern detection.
- Automated suggestions.

Phase 5 - Admin Dashboard:

- Rule visibility and emergency override.
- Analytics.

Phase 6 - Enterprise Deployment:

- Authentication.
- Multi-user rollout.
- Security hardening.

Phase 7 - Advanced Intelligence and Local Hotel-Specific Model Training:

- Historical completed-email importer.
- Privacy-preserving PII redaction and sanitization.
- AI-assisted batch labeling for sanitized historical examples.
- Human review sampling for labels.
- Supabase training dataset.
- Local classifier training pipeline.
- Versioned local model artifacts.
- Confidence-based routing with external AI fallback.
- Feedback-driven retraining.
- Admin controls for import, labeling, training, activation, rollback, and metrics.

## Phase 7 - Advanced Intelligence and Local Hotel-Specific Model Training

### Purpose

Phase 7 is the long-term intelligence layer for ReplyRight.

The goal is to evolve ReplyRight from an API-dependent AI email assistant into a hotel-specific operational intelligence system that can classify routine emails locally, learn from historical completed emails, improve from user feedback, and reduce ongoing OpenAI/Claude API costs.

The objective is not to train a full large language model from scratch. That would be expensive, unnecessary, and impractical for this project.

Instead, ReplyRight should build a hybrid learning system:

```text
Rules
+
Supabase feedback database
+
Historical labeled email examples
+
Embeddings
+
Small local classification models
+
Optional external AI fallback
```

This allows ReplyRight to become specifically trained for luxury hotel email workflows without requiring every email to be sent to an external AI API.

### Strategic Goal

By the end of Phase 7, ReplyRight should be able to classify most routine hotel emails locally for:

- Urgency.
- Department or task owner.
- Email category.
- Operational status.
- Missing information.
- Whether a reply is needed.
- Whether escalation is required.

External AI models should eventually be used only for:

- Low-confidence classifications.
- Complex reasoning.
- Long-form summarization.
- Polished guest-facing reply drafting.
- Unusual or sensitive cases.
- New patterns the local model has not learned yet.

The long-term goal is to make API usage optional or minimal, not mandatory for every email.

### Target Architecture

```text
Historical Completed Emails
    -> Email Importer
    -> PII Redaction and Sanitization Layer
    -> AI-Assisted Batch Labeling
    -> Human Review Sampling
    -> Supabase Training Dataset
    -> Local Model Training Pipeline
    -> Versioned Local Classifiers
    -> Confidence-Based Routing
    -> Routine Emails Classified Locally
    -> Low-Confidence Emails Sent to External AI
    -> User Feedback Saved Back to Supabase
    -> Periodic Retraining
```

### What Training Means In This Project

Phase 7 should distinguish between three concepts.

1. Fine-tuning

Fine-tuning means teaching an existing AI model to follow ReplyRight's hotel-specific labeling patterns.

This may be useful later, but it should not be the first approach because it may still require paid API usage and may not be easy to run locally.

2. Local classification model

This is the preferred first approach.

ReplyRight should train lightweight local models that predict structured labels such as urgency, owner, category, and status.

These models do not need to write emails. They only need to classify emails.

3. Retrieval-based learning

ReplyRight should store sanitized examples of previously completed and corrected emails. When a new email arrives, the app can retrieve similar historical examples and use them to guide classification.

This can improve accuracy without retraining a large model.

The recommended Phase 7 strategy is:

```text
Local classification model
+
Retrieval-based learning
+
Rules
+
External AI fallback
```

### What Should Be Classified Locally

The local model should initially predict structured fields only.

Local prediction targets:

- `urgency_score`: 1-5.
- `owner`: Reservations, Concierge, Front Desk, Sales, Housekeeping, Engineering, All Departments, Other.
- `category`: Payment, Rate, VIP, Amenity, Confirmation, Complaint, Modification, Cancellation, Group, Billing, General.
- `status`: Needs Reply, No Reply Needed, Waiting on Guest, Waiting on Internal Team, Completed, Escalate.
- `missing_information`: true/false.
- `reply_required`: true/false.
- `escalation_required`: true/false.

Owner labels should continue to prefer the current operating-department taxonomy. Finance and Leadership can be studied as future labels only if Brian explicitly adds them to ReplyRight's routing model.

The local model should not initially be responsible for polished reply writing.

### What Should Continue Using External AI

External AI should remain available for:

- Complex summary generation.
- Guest-facing reply drafting.
- Multi-email thread reasoning.
- Sensitive complaint handling.
- VIP nuance.
- Ambiguous ownership.
- Legal, safety, payment, accessibility, or escalation-sensitive cases.

Eventually, local AI may assist with these areas, but the first local training goal is classification, not writing.

### Historical Email Importer

Build a historical email importer that can process completed emails from:

- Outlook completed folders.
- Local `.eml` files.
- Exported mailbox data.
- CSV exports if available.
- Existing app email cache if present.

The importer should allow the user/admin to select:

- Date range.
- Folder source.
- Maximum number of emails.
- Include replies yes/no.
- Include sent responses yes/no.
- Import completed-only emails yes/no.

The importer should default to completed or closed email threads because they are more useful for training.

### Privacy And PII Protection

Raw hotel emails must not be stored in the training database by default.

Before any email is stored, labeled, embedded, or used for model training, the system must pass it through a redaction layer.

Default redaction requirements:

- Guest names.
- Confirmation numbers.
- Reservation numbers.
- Hilton Honors numbers.
- Email addresses.
- Phone numbers.
- Credit card or payment details.
- Home or business addresses.
- Passport or ID information.
- VIP identifiers.
- Internal employee names where not needed.
- Attachments.
- Sertifi links.
- Payment links.
- Folio numbers.
- Case numbers.
- Loyalty account numbers.
- Free-form personal details.

Replace sensitive values with placeholders:

- `[GUEST_NAME]`
- `[CONFIRMATION_NUMBER]`
- `[EMAIL]`
- `[PHONE]`
- `[PAYMENT_LINK]`
- `[HONORS_NUMBER]`
- `[DATE]`
- `[ROOM_TYPE]`
- `[RATE]`
- `[AGENCY_NAME]`
- `[EMPLOYEE_NAME]`

Example:

```text
Original:
Please send the payment link for Ms. Ding, Yuanyuan, confirmation 3470803259, arriving May 22.

Sanitized:
Please send the payment link for [GUEST_NAME], confirmation [CONFIRMATION_NUMBER], arriving [DATE].
```

Store the operational pattern, not sensitive personal data.

### Sanitized Training Record

Each imported email should become a sanitized training record.

Example structure:

```json
{
  "email_hash": "sha256_hash",
  "thread_hash": "sha256_hash",
  "sender_domain": "travelagency.com",
  "sanitized_subject": "Payment link request for upcoming stay",
  "sanitized_body": "Please send the payment link for [GUEST_NAME], confirmation [CONFIRMATION_NUMBER], arriving [DATE].",
  "detected_language": "en",
  "source_folder": "Completed",
  "date_bucket": "2026-05",
  "has_attachment": false,
  "contains_payment_language": true,
  "contains_vip_language": false,
  "contains_complaint_language": false,
  "contains_arrival_soon": true,
  "created_at": "timestamp"
}
```

### AI-Assisted Batch Labeling

Use an external AI model to label historical sanitized emails in batches.

The labeling output should be structured JSON only.

Each labeled email should receive:

- `urgency_score`
- `owner`
- `category`
- `status`
- `missing_information`
- `reply_required`
- `escalation_required`
- `reasoning_summary`
- `label_confidence`

Example output:

```json
{
  "urgency_score": 4,
  "owner": "Reservations",
  "category": "Payment",
  "status": "Needs Reply",
  "missing_information": false,
  "reply_required": true,
  "escalation_required": false,
  "reasoning_summary": "The sender is requesting a secure payment link for an upcoming reservation.",
  "label_confidence": 0.91
}
```

### Human Review Sampling

Do not blindly trust AI-generated labels.

Build an admin review queue that samples:

- Random 5-10% of AI-labeled emails.
- All labels with confidence below 0.75.
- All urgency 5 labels.
- All `escalation_required = true` labels.
- All unclear owner/category labels.

The admin should be able to approve or correct the labels. Corrected labels should override AI labels in training.

### Supabase Tables For Phase 7

Add the following tables to Supabase if they do not already exist.

`training_emails` stores sanitized imported emails.

Suggested fields:

- `id uuid primary key`
- `email_hash text unique`
- `thread_hash text`
- `sender_domain text`
- `sanitized_subject text`
- `sanitized_body text`
- `detected_language text`
- `source_folder text`
- `date_bucket text`
- `has_attachment boolean`
- `contains_payment_language boolean`
- `contains_vip_language boolean`
- `contains_complaint_language boolean`
- `contains_arrival_soon boolean`
- `created_at timestamptz`

`training_labels` stores AI-generated and human-corrected labels.

Suggested fields:

- `id uuid primary key`
- `training_email_id uuid references training_emails(id)`
- `urgency_score int`
- `owner text`
- `category text`
- `status text`
- `missing_information boolean`
- `reply_required boolean`
- `escalation_required boolean`
- `reasoning_summary text`
- `label_confidence numeric`
- `label_source text`
- `reviewed_by_human boolean`
- `reviewed_by text`
- `reviewed_at timestamptz`
- `created_at timestamptz`

Allowed `label_source` values:

- `ai_batch_label`
- `human_review`
- `user_feedback`
- `rule_engine`

`model_versions` tracks trained local models.

Suggested fields:

- `id uuid primary key`
- `model_name text`
- `model_type text`
- `version text`
- `trained_at timestamptz`
- `training_dataset_size int`
- `active boolean`
- `artifact_path text`
- `notes text`
- `created_at timestamptz`

`model_metrics` tracks model performance.

Suggested fields:

- `id uuid primary key`
- `model_version_id uuid references model_versions(id)`
- `target_label text`
- `accuracy numeric`
- `precision numeric`
- `recall numeric`
- `f1_score numeric`
- `confusion_matrix jsonb`
- `test_dataset_size int`
- `created_at timestamptz`

`prediction_logs` tracks local model predictions.

Suggested fields:

- `id uuid primary key`
- `email_hash text`
- `model_version_id uuid references model_versions(id)`
- `predicted_urgency int`
- `predicted_owner text`
- `predicted_category text`
- `predicted_status text`
- `confidence_urgency numeric`
- `confidence_owner numeric`
- `confidence_category numeric`
- `confidence_status numeric`
- `used_external_ai boolean`
- `final_source text`
- `created_at timestamptz`

`human_review_queue` stores low-confidence or sensitive records for review.

Suggested fields:

- `id uuid primary key`
- `training_email_id uuid references training_emails(id)`
- `reason text`
- `priority int`
- `status text`
- `assigned_to text`
- `created_at timestamptz`
- `reviewed_at timestamptz`

Allowed `status` values:

- `pending`
- `reviewed`
- `dismissed`

### Local Model Strategy

The first implementation should not use a large local LLM.

Start with:

```text
sentence-transformers embeddings
+
LogisticRegression or LinearSVM
```

Optional later upgrades:

- XGBoost.
- LightGBM.
- Small transformer classifier.
- Local LLM with LoRA fine-tuning.
- ONNX-optimized classifier.

Initial model targets should be separate classifiers:

- `urgency_model.pkl`
- `owner_model.pkl`
- `category_model.pkl`
- `status_model.pkl`
- `missing_info_model.pkl`
- `reply_required_model.pkl`
- `escalation_model.pkl`

Each classifier should be independently trainable and independently evaluated.

### Feature Engineering

The model should use a combination of:

- Text embeddings.
- Sender domain.
- Email subject.
- Detected language.
- Arrival date proximity if available.
- Contains payment language.
- Contains complaint language.
- Contains VIP language.
- Contains cancellation language.
- Contains rate language.
- Contains group language.
- Thread length.
- Whether leadership is copied.
- Whether guest is in-house.
- Whether arrival is today/tomorrow.

Keep the first version simple:

- `sanitized_subject + sanitized_body`
- `sender_domain`
- Keyword flags

### Confidence-Based Routing

When analyzing a new email, ReplyRight should use the local classifier first.

Suggested thresholds:

- High confidence: greater than `0.85`.
- Medium confidence: `0.60` to `0.85`.
- Low confidence: below `0.60`.

Routing behavior:

```text
If confidence > 0.85:
    use local prediction

If confidence is between 0.60 and 0.85:
    use local prediction
    mark as review suggested

If confidence < 0.60:
    call external AI
    save result for future training
```

Sensitive cases should always be eligible for external AI or human review even if the local classifier is confident.

Sensitive triggers include:

- Payment dispute.
- Legal threat.
- Chargeback.
- Accessibility issue.
- Medical issue.
- Security issue.
- High-profile VIP.
- Leadership escalation.
- Guest complaint with compensation request.

### Feedback Loop

Every user correction should feed the training system.

When a user changes any of the following, save the correction to Supabase:

- Urgency.
- Owner.
- Category.
- Status.
- Missing information.
- Reply required.
- Escalation required.

Corrections should become high-value training labels because they represent real human judgment.

User feedback should be weighted higher than AI-generated labels.

Suggested weighting:

- Human correction: highest trust.
- Admin-reviewed label: high trust.
- Rule-generated label: medium trust.
- AI batch label: lower trust.

### Retraining Workflow

Add an admin tool for retraining.

The admin should be able to:

- Select training date range.
- Include/exclude AI-only labels.
- Require human-reviewed labels only.
- Set minimum confidence.
- Train models.
- View metrics.
- Activate new model version.
- Roll back to previous model version.

Recommended retraining cadence:

- Manual during development.
- Weekly during pilot.
- Monthly once stable.
- Immediate retraining after major rule changes.

### Model Activation And Rollback

New model versions should not automatically replace active models without evaluation.

Workflow:

1. Train candidate model.
2. Evaluate against test set.
3. Show metrics in admin dashboard.
4. Compare to active model.
5. Admin approves activation.
6. App downloads or loads new active model.
7. Old model remains available for rollback.

Rollback must be available if the new model performs worse in production.

### Evaluation Metrics

Track metrics separately for each prediction target.

For urgency:

- Accuracy.
- Mean absolute error.
- Confusion matrix.
- Percentage within 1 urgency level.

For owner/category/status:

- Accuracy.
- Precision.
- Recall.
- F1 score.
- Confusion matrix.

Also track operational metrics:

- Percentage of emails handled locally.
- Percentage requiring external AI.
- Percentage corrected by users.
- Most common correction type.
- Most misclassified sender domains.
- Most misclassified categories.
- API cost reduction estimate.

### Admin Dashboard Additions

Add a Phase 7 section to the admin dashboard.

It should include:

- Training dataset size.
- Number of labeled examples.
- Number of human-reviewed labels.
- Current active model version.
- Latest model metrics.
- Local classification success rate.
- External AI fallback rate.
- Correction rate.
- API cost saved estimate.
- Button to import historical emails.
- Button to run redaction.
- Button to batch label sanitized emails.
- Button to review labels.
- Button to train local model.
- Button to activate model version.
- Button to roll back model version.

### Cost Reduction Goal

The goal is not immediate zero API usage.

Target reduction path:

- Initial state: external AI handles nearly all analysis.
- After first historical training batch: local model handles 30-50% of routine classification.
- After several weeks of feedback: local model handles 60-80% of routine classification.
- Long term: external AI is used mainly for low-confidence or complex cases.

Reply drafting may continue to use external AI longer than classification.

### Zero-API Long-Term Option

If the goal becomes complete removal of external AI costs, add optional support for local LLMs.

Possible future tools:

- Ollama.
- `llama.cpp`.
- LM Studio.
- Local quantized models.
- Small instruction-tuned open-source models.

Use local LLMs only after the classification system is stable.

Local LLMs may help with:

- Basic summaries.
- Internal notes.
- Rough draft replies.
- Classification explanations.

External AI will likely remain stronger for polished guest-facing responses unless the local model is carefully selected and tested.

### Safety Requirement

Phase 7 must be privacy-preserving by default.

Do not store or train on raw guest emails unless an explicit developer/admin override is enabled.

Default behavior must be:

```text
import
redact
sanitize
hash
label
review
train
evaluate
activate
```

Raw text should be discarded after sanitization unless explicitly retained locally for debugging.

### Recommended Phase 7 Subphases

Phase 7A - Historical Import and Redaction:

- Historical email importer.
- PII redactor.
- Sanitized training record creator.
- Supabase upload for `training_emails`.

Phase 7B - AI-Assisted Labeling:

- Batch labeler.
- Structured JSON label output.
- Retry/error handling.
- Label confidence storage.
- `training_labels` table integration.

Phase 7C - Human Review Queue:

- Admin label review screen.
- Correction controls.
- Approve/reject label workflow.
- Sampling rules.
- Review status tracking.

Phase 7D - Local Classifier Training:

- Embedding generator.
- Train/test split.
- Classifier training scripts.
- Model artifact storage.
- `model_metrics` generation.
- `model_versions` table integration.

Phase 7E - Runtime Local Prediction:

- Local model loader.
- Local classification service.
- Confidence scoring.
- External AI fallback.
- Prediction logging.
- Review-suggested flag.

Phase 7F - Continuous Learning:

- Feedback-to-training conversion.
- Weekly/manual retraining.
- Model comparison.
- Activation and rollback.
- Performance dashboard.

Phase 7G - Optional Local LLM Support:

- Ollama or `llama.cpp` integration.
- Local summary generation.
- Local rough reply drafting.
- External AI fallback for polished output.

Build Phase 7G only after classification is stable.

### Definition Of Done For Phase 7

Phase 7 is complete when:

- Historical completed emails can be imported safely.
- PII is redacted before storage or labeling.
- Sanitized emails can be batch-labeled by external AI.
- Labels can be reviewed and corrected by an admin.
- Local classifiers can be trained from labeled examples.
- Model metrics are visible in the admin dashboard.
- New model versions can be activated or rolled back.
- Routine emails can be classified locally.
- Low-confidence emails fall back to external AI.
- User feedback is added to future training data.
- API usage for classification is measurably reduced.

### Codex Implementation Instruction

Implement Phase 7 incrementally. Do not attempt to build the entire local AI system in one pass.

Preferred order:

1. Add Supabase tables and migrations for Phase 7.
2. Build sanitized training email data model.
3. Build PII redaction service.
4. Build historical importer.
5. Build AI-assisted batch labeler.
6. Build human review queue.
7. Build local classifier training script.
8. Build runtime local prediction service.
9. Add admin dashboard controls.
10. Add model activation and rollback.
11. Add performance metrics and API cost reduction tracking.

Maintain modular design so this system can be tested independently from the main email analysis UI.

## Long-Term Vision

ReplyRight evolves from a personal productivity tool into a shared operational intelligence platform for luxury hospitality organizations.

Potential future capabilities:

- Fine-tuned classification models.
- Single-hotel rule refinement for Waldorf Astoria New York.
- Local hotel-specific classifiers for routine triage.
- Retrieval-based learning from sanitized historical examples.
- Department-specific prompts.
- SLA tracking.
- Response time analytics.
- Team productivity dashboards.

## Master Codex Prompt For Future Agents

Read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` and use it as the architectural source of truth for ReplyRight.

ReplyRight is a desktop AI assistant for Outlook that prioritizes emails, assigns task ownership, summarizes required actions, identifies missing information, and drafts luxury-hospitality responses.

The application uses Supabase as a centralized shared-learning database so feedback from all users improves performance across all installations.

Implement structured feedback capture, 1-5 summary/reply quality ratings, rule candidate generation, hands-off rule auto-promotion, startup synchronization, local caching, and a staged OpenAI refresh pipeline consisting of fact extraction, sender detection, action detection, owner assignment, urgency scoring, missing-information detection, summary generation, and required-action generation. Claude Opus is reserved for explicit `AI Suggestion` reply drafting/refinement.

Phase 7 adds a privacy-preserving local learning path: historical completed-email import, PII redaction, AI-assisted batch labeling, human review sampling, Supabase training tables, local embedding/classifier training, confidence-based external AI fallback, model versioning, rollback, and feedback-driven retraining.

Do not store guest PII, reservation numbers, payment details, or raw email bodies unless explicitly enabled.

Maintain enterprise-grade architecture, modular design, strong typing, logging, and test coverage.
