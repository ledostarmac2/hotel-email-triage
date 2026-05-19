# Implementation Plan

## Phase 1: Reference Review and Architecture

Status: complete in this repository.

Deliverables:

- Review `/reference/inbox-zero`, `/reference/email-agent`, and `/reference/intelligent-email-assistant`.
- Produce `ARCHITECTURE.md`.
- Produce `RECOMMENDATIONS.md`.
- Scaffold `/app`.

## Phase 2: Application Foundation

Status: scaffolded.

Tasks:

- Build a Next.js TypeScript app in `/app`.
- Add Prisma schema for mailbox state, email messages, classifications, action logs, category mappings, manual overrides, and feedback.
- Add environment validation for Microsoft Graph, OpenAI, database, and automation settings.
- Add Docker support for app plus PostgreSQL.
- Add a health endpoint.

Acceptance criteria:

- `npm install` works inside `/app`.
- `npx prisma generate` succeeds.
- `npm run dev` starts the dashboard.
- `GET /api/health` returns service status.

## Phase 3: Microsoft Graph Shared Mailbox Connection

Tasks:

- Configure Azure app registration with application permissions.
- Restrict mailbox access to `Reservations@waldorfastoria.com` using an Exchange Application Access Policy.
- Implement app-only token acquisition with client credentials.
- Read unread inbox messages from the shared mailbox.
- Normalize subject, sender, recipients, cc, body preview, body, received time, categories, read state, flag state, and attachment metadata.
- Persist fetched messages.

Acceptance criteria:

- `POST /api/sync/unread` fetches unread messages and upserts them.
- `GET /api/emails/unread` returns stored unread messages.
- No reference project code is copied into `/app`.

## Phase 4: Redaction and AI Classification

Tasks:

- Implement Luhn-aware credit card detection.
- Redact payment card numbers, CVV-like phrases, expiration dates, and sensitive authorization text before AI calls.
- Implement deterministic trigger detection before model classification.
- Call OpenAI with a strict hotel reservations classification schema.
- Persist prompt version, model, redaction counts, trigger evidence, and classification output.

Acceptance criteria:

- Full card numbers are replaced before AI transmission.
- Classification JSON matches the required priority/category/deadline/color format.
- Critical triggers can override weaker AI classifications.

## Phase 5: Outlook Category and Flag Automation

Tasks:

- Ensure required Outlook master categories exist.
- Map classification to one or more Outlook categories.
- Apply categories to messages.
- Optionally set follow-up flags/reminders for Critical and High messages.
- Store each Graph mutation in the action log.

Acceptance criteria:

- Critical messages receive `Red - Critical`.
- Payment messages receive `Green - Payment Needed`.
- VIP messages receive `Purple - VIP`.
- Failed Graph mutations are logged and retryable.

## Phase 6: Dashboard UI

Tasks:

- Build unread queue view.
- Add priority summary cards.
- Add category summary cards.
- Add critical arrivals today, VIP guests, payment pending, and complaint escalation panels.
- Add search and filtering.
- Add manual recategorization.

Acceptance criteria:

- Reservations agents can see the highest-priority work first.
- Manual override changes are persisted and visible in the action log.

## Phase 7: Analytics and Feedback

Tasks:

- Track classification volume by priority, category, sender domain, and hour.
- Track override rate and reason.
- Add export/reporting endpoints.
- Feed manual overrides into future prompt examples or fine-tuning dataset.

Acceptance criteria:

- Managers can identify bottlenecks and common inquiry types.
- Prompt changes can be evaluated against historical overrides.

## Production Hardening

Before live mailbox automation:

- Add authentication and RBAC.
- Add audit log retention policy.
- Add encrypted secret management.
- Add Graph webhook support or scheduled worker deployment.
- Add integration tests against a Microsoft Graph test mailbox.
- Add model evaluation fixtures with real-world redacted examples.
- Add dry-run mode and approval gate for automatic category writes.
