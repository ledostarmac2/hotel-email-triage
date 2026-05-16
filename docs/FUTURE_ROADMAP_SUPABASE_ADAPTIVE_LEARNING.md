# ReplyRight Future Roadmap: Supabase Adaptive Learning

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
| Desktop application | Python + PySide6 |
| AI engine | OpenAI API |
| Central database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth |
| Local cache | JSON / SQLite |
| Version control | GitHub |
| IDE | VS Code |
| Primary coding agent | Codex |

Note: the current working desktop app is FastAPI + pywebview/WebView2. Treat PySide6 as the future target only after a deliberate migration plan.

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

## Long-Term Vision

ReplyRight evolves from a personal productivity tool into a shared operational intelligence platform for luxury hospitality organizations.

Potential future capabilities:

- Fine-tuned classification models.
- Single-hotel rule refinement for Waldorf Astoria New York.
- Department-specific prompts.
- SLA tracking.
- Response time analytics.
- Team productivity dashboards.

## Master Codex Prompt For Future Agents

Read `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md` and use it as the architectural source of truth for ReplyRight.

ReplyRight is a desktop AI assistant for Outlook that prioritizes emails, assigns task ownership, summarizes required actions, identifies missing information, and drafts luxury-hospitality responses.

The application uses Supabase as a centralized shared-learning database so feedback from all users improves performance across all installations.

Implement structured feedback capture, 1-5 summary/reply quality ratings, rule candidate generation, hands-off rule auto-promotion, startup synchronization, local caching, and a staged OpenAI refresh pipeline consisting of fact extraction, sender detection, action detection, owner assignment, urgency scoring, missing-information detection, summary generation, and required-action generation. Claude Opus is reserved for explicit `AI Suggestion` reply drafting/refinement.

Do not store guest PII, reservation numbers, payment details, or raw email bodies unless explicitly enabled.

Maintain enterprise-grade architecture, modular design, strong typing, logging, and test coverage.
