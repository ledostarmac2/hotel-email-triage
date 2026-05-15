# Waldorf Astoria Reservations Email Triage Architecture

## Reference Review

The `/reference` projects were reviewed as architectural input only. The production application for this repository lives in `/app`.

### Inbox Zero

Inbox Zero is the best primary reference for this project because it already models a modern email automation product with Outlook support, AI-driven email decisions, provider abstractions, webhooks, retry handling, category operations, a Next.js application, Prisma, PostgreSQL, and background processing.

Useful concepts to adopt:

- Provider boundary around Microsoft Graph operations so Outlook-specific logic does not leak into dashboard or AI code.
- Microsoft Graph token refresh, retry, throttling, immutable message ID preference, and category creation/application patterns.
- Separate email parsing/normalization from AI decisioning.
- Store rule/classification decisions and automation execution history in the database.
- Use a web dashboard and API routes in the same Next.js app for early phases, with room to extract workers later.
- Subscription renewal logic for Graph change notifications after the polling-based MVP.

Concepts to avoid copying directly:

- Inbox Zero is a broad consumer/team product. This project should not inherit unrelated billing, newsletter, multi-provider, marketing, or generalized assistant complexity.
- Its prompt/rule sync history is powerful but heavier than needed for phase 1. This project should use a fixed hotel reservations taxonomy first, then add overrides and feedback.

### email-agent

email-agent is useful as a conceptual model for a clean processing pipeline and learning loop. It separates collection, categorization, summarization, triage, rules, and feedback. Its CLI/TUI and Gmail-specific code are less relevant.

Useful concepts to adopt:

- Pipeline stages: collect, normalize, redact, classify, persist, apply actions, log outcome.
- Explicit priority scoring and explanation fields.
- Manual feedback/retraining records for future model improvement.
- Testable domain models for emails, categories, priorities, rules, and decisions.

Concepts to avoid copying directly:

- Gmail-first assumptions.
- General personal assistant categories that do not match hotel reservations operations.
- Multi-agent orchestration until there is a demonstrated need. A deterministic pre-classifier plus one structured AI classification call is simpler and safer.

### intelligent-email-assistant

This project is useful mostly as an enterprise Microsoft 365 sketch. It describes Microsoft Graph, scheduled processing, PostgreSQL, notifications, and an admin dashboard. Its Graph service is largely stubbed, so it is not a strong implementation source.

Useful concepts to adopt:

- Enterprise configuration posture: tenant ID, client ID, client secret, shared mailbox address, database URL, AI provider key.
- Scheduled email processing and health checks.
- Web dashboard statistics and operational views.

Concepts to avoid copying directly:

- Stubbed Microsoft Graph implementation.
- Auto-response behavior. The Waldorf Astoria use case is triage and category application, not autonomous guest responses.
- WhatsApp/mobile scope for the initial product.

## Recommended Production Shape

Build `/app` as a focused Next.js full-stack application:

- Frontend: Next.js App Router, React, TypeScript.
- Backend: Next.js route handlers and server modules.
- Database: PostgreSQL with Prisma.
- AI: OpenAI structured JSON classification.
- Microsoft 365: Microsoft Graph app-only auth for the shared mailbox.
- Runtime: Docker Compose for local Postgres plus app container.

The application should be organized around domain boundaries:

```text
app/
  prisma/
    schema.prisma
  src/
    app/
      api/
      page.tsx
      layout.tsx
    components/
    lib/
      ai/
      graph/
      security/
      triage/
      db.ts
      env.ts
```

## Data Flow

1. A sync job or API route reads unread messages from `Reservations@waldorfastoria.com`.
2. Microsoft Graph returns message metadata, recipients, body preview/body, categories, read state, flags, and attachment metadata.
3. The app normalizes the Graph message into an internal `EmailMessage`.
4. Sensitive payment data is redacted before AI classification.
5. A deterministic pre-classifier checks hard triggers such as arrival today/tomorrow, VIP/owner indicators, urgent language, payment authorization language, copied executives, and complaint language.
6. OpenAI receives only redacted message content and returns strict JSON:

```json
{
  "priority": "Critical",
  "category": "Payment Needed / CCA / Sertifi",
  "reason": "Reservation cannot be confirmed until payment authorization is received.",
  "recommended_deadline": "Within 1 hour",
  "suggested_category_color": "Green"
}
```

7. The app persists the email, redaction summary, classification, trigger evidence, model metadata, and action log.
8. If automation is enabled, the app ensures Outlook categories exist and applies category names/flags to the shared mailbox message.
9. Dashboard users review queues, summaries, and critical work. Manual overrides are stored as feedback for future tuning.

## Microsoft Graph Strategy

For a shared mailbox coordinator, use application permissions rather than delegated per-user tokens:

- `Mail.ReadWrite` application permission for reading unread messages and applying categories/flags.
- `MailboxSettings.ReadWrite` only if category management requires it in the tenant setup.
- Admin consent in the Waldorf Astoria tenant.
- Restrict the application to `Reservations@waldorfastoria.com` with an Exchange Application Access Policy.

Graph endpoints should use `/users/{sharedMailbox}/...` rather than `/me/...`.

Important endpoints:

- `GET /users/{mailbox}/mailFolders/inbox/messages?$filter=isRead eq false`
- `GET /users/{mailbox}/messages/{id}?$select=...&$expand=attachments(...)`
- `PATCH /users/{mailbox}/messages/{id}` for categories and flags.
- `GET /users/{mailbox}/outlook/masterCategories`
- `POST /users/{mailbox}/outlook/masterCategories`

Use `Prefer: IdType="ImmutableId"` so stored message IDs remain stable.

## Security Model

Security is a product feature, not a later cleanup:

- Never send raw credit card numbers to OpenAI.
- Redact PANs using a Luhn-aware detector before classification.
- Redact CVV, expiration dates, authorization form links/tokens when detected.
- Store raw email body only if explicitly enabled. The scaffold defaults to storing sanitized content.
- Encrypt secrets through platform secret storage in production.
- Log every classification and Outlook mutation.
- Implement role-based access before production rollout:
  - Admin: configure mailbox, credentials, category mappings.
  - Manager: override classifications, view analytics.
  - Agent: view queue and mark manual outcomes.

## Category Mapping

Recommended first mapping:

| Priority/Category Signal | Outlook Category |
| --- | --- |
| Critical | Red - Critical |
| High | Orange - High Priority |
| Agent Quote Request | Blue - Sales Quote |
| Payment Needed / CCA / Sertifi | Green - Payment Needed |
| VIP / Owner / Celebrity | Purple - VIP |
| Low Priority / Internal FYI | Gray - Low Priority |

Multiple categories can be applied when useful, for example `Red - Critical` and `Green - Payment Needed`.

## Deployment Shape

Phase 1 can run as one Next.js app plus PostgreSQL. For production, add a worker process for scheduled sync and Graph webhook processing:

- Web app: dashboard, API, admin configuration.
- Worker: polling/webhooks, AI classification, Outlook actions.
- PostgreSQL: durable state, classification log, overrides, action audit.
- Optional Redis/BullMQ later if queue throughput or retry control requires it.
