> Historical archive. Do not use this as current project state. Use docs/CURRENT_STATE.md, docs/HANDOFF.md, and docs/V1_RELEASE_PLAN.md instead.

# Recommendations

## Recommended Stack

Use a focused TypeScript stack:

- Next.js App Router for dashboard and API routes.
- Prisma with PostgreSQL for durable state.
- Microsoft Graph REST calls with app-only authentication.
- OpenAI JSON classification with strict validation.
- Docker Compose for local development.

This keeps the product close to Inbox Zero's proven architecture while avoiding monorepo complexity that is unnecessary for a single shared mailbox workflow.

## Design Principles

- Treat `Reservations@waldorfastoria.com` as the core product surface, not as a generic email account.
- Start with deterministic hotel rules plus AI judgment, not unconstrained AI routing.
- Store every decision with evidence.
- Apply Outlook categories only after the classification result has been saved.
- Keep manual overrides first-class because they become the training signal.
- Default to dry-run until Microsoft permissions, category mappings, and redaction are verified.

## What To Borrow From Each Reference

### Borrow From Inbox Zero

- Outlook provider abstraction.
- Graph retry and throttling discipline.
- Category creation and message patching model.
- Webhook/subscription renewal concepts.
- Prisma-backed event/action history.
- Next.js dashboard plus API architecture.

### Borrow From email-agent

- Pipeline-oriented thinking.
- Explicit `priority`, `category`, `summary/reason`, `action`, and `feedback` records.
- Attention scoring and human-readable explanations.
- User feedback loop for future retraining.

### Borrow From intelligent-email-assistant

- Enterprise Microsoft 365 configuration.
- Scheduled processor concept.
- Admin dashboard/statistics concept.
- Multi-provider AI fallback as a possible later enhancement.

## What Not To Borrow

- Do not copy Inbox Zero's unrelated billing, newsletter, calendar, or generalized assistant features.
- Do not copy Gmail-oriented assumptions from email-agent.
- Do not use intelligent-email-assistant's stubbed Graph service as implementation code.
- Do not implement autonomous guest replies in the first production version.

## Microsoft 365 Setup Recommendation

Use application permissions for the backend service:

1. Create an Azure app registration.
2. Add Microsoft Graph application permission `Mail.ReadWrite`.
3. Grant admin consent.
4. Create a client secret or certificate.
5. Restrict access with an Exchange Application Access Policy to `Reservations@waldorfastoria.com`.
6. Configure `/app/.env` with tenant, client, secret, and shared mailbox address.

This is more appropriate for a shared departmental mailbox than requiring an individual reservations agent to keep delegated OAuth tokens active.

## AI Classification Recommendation

Use a two-layer classifier:

1. Deterministic trigger detection:
   - arrival today/tomorrow,
   - VIP/owner/celebrity,
   - urgent language,
   - payment needed to secure reservation,
   - high-value complaint,
   - executive copied.
2. OpenAI structured classification:
   - priority,
   - business category,
   - reason,
   - recommended deadline,
   - suggested Outlook color.

The deterministic layer should be allowed to escalate to Critical even if the model returns a lower priority.

## Redaction Recommendation

Implement redaction before any AI call:

- Luhn-valid card numbers become `[REDACTED_CARD]`.
- CVV phrases become `[REDACTED_CVV]`.
- Expiration dates become `[REDACTED_EXPIRY]`.
- Sensitive payment authorization phrases should keep business meaning while removing secrets.

Persist redaction counts, not raw sensitive values.

## Dashboard Recommendation

The dashboard should feel like an operations console:

- Dense queue first.
- Priority and category summaries at top.
- Critical arrivals, VIPs, payment pending, and complaint escalations as active work views.
- Search and filters for agents.
- Manual recategorization for managers/admins.

Avoid a marketing-style landing page. The first screen should be the reservations work queue.

## Suggested Initial Environment Variables

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hotel_email_triage
MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_SHARED_MAILBOX=Reservations@waldorfastoria.com
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
TRIAGE_DRY_RUN=true
```

## Near-Term Risks

- Microsoft Graph application permissions are powerful. Restrict mailbox scope before production.
- Outlook categories are mailbox-level state. Handle existing category name/color conflicts carefully.
- AI may over-prioritize luxury travel keywords. Use deterministic triggers and manual override feedback to tune.
- Payment-related messages are high-risk. Redaction must be tested with realistic CCA/Sertifi examples before enabling AI calls.
