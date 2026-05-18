# Security And Privacy

Last updated: 2026-05-18

## Core Posture

ReplyRight is a local-first, human-supervised, read-only Outlook triage app.

The app may read/import emails and update local SQLite state. It must not send, delete, archive, move, categorize, mark read, or otherwise mutate Outlook messages without a new explicit approval workflow.

## Data Boundaries

```text
Outlook
  -> local ReplyRight process
  -> local SQLite under data/
  -> optional Supabase metadata/training tables
  -> optional external AI providers
  -> GitHub releases for app updates
```

Local mailbox content and runtime data stay under ignored runtime folders by default.

## Never Commit

- `.env`
- `dist\ReplyRight\.env`
- `data\*`
- `dist\ReplyRight\data\*`
- SQLite databases
- `.msg` exports
- startup logs
- service-role keys
- session cookies
- raw mailbox exports
- EXE binaries
- build/vendor/venv folders

## Logging Rules

Do not log:

- Raw email bodies
- Full message threads
- Guest names
- Email addresses
- Phone numbers
- Confirmation or reservation numbers
- Credit card or payment details
- Service-role keys
- Session cookies
- Full AI prompts containing mailbox content

Application modules should use `runtime_log.get_logger()` and log concise operational metadata only.

## Redaction

`outlook_dashboard/redaction.py` redacts payment-like and sensitive identifiers before training export and external AI use.

Coverage includes:

- Luhn-valid credit card numbers
- CVV/security code phrases
- Expiration date phrases
- Payment links
- Email addresses
- Phone-like values
- Confirmation-number labels, including selected localized variants

Do not weaken redaction to improve model accuracy. Improve redaction coverage instead.

## External AI Policy

Refresh Inbox:

- OpenAI first when configured.
- Google AI fallback when configured and OpenAI is unavailable.
- Deterministic local fallback when no refresh AI is configured or an AI call fails.

Claude:

- Reserved for explicit single-email Analyze/AI Suggestion.
- Allowed for admin-explicit training refinement when `refine=true`.
- Must not be used for bulk Refresh Inbox.

AI-generated replies are suggestions only. A human must review before using them.

## Supabase Policy

Supabase Auth handles app login.

Supabase data roles:

- `feedback_events`: correction metadata, no raw mailbox content.
- `classification_rules`: shared approved/pending/rejected rules.
- `known_senders`: sender-domain mappings.
- `prompt_versions`: prompt/config text with no mailbox content.
- `training_examples`: redacted bodies and labels, service-role only.

Do not print the service-role key. Do not expose `training_examples` through the anon key.

## Training Data Rules

Training records may include:

- sender domain
- sanitized subject tokens
- redacted latest-message body
- labels and review metadata
- hashed fingerprint

Training records must not include:

- raw body
- full subject
- full sender email
- full recipient list
- attachments
- unredacted reservation identifiers
- payment details
- unredacted guest personal details

## Authentication

Login uses Supabase Auth. The `rr_session` cookie is HttpOnly and stores access/refresh token data for server-side validation and refresh.

Admin routes must stay protected by auth middleware.

Password reset/invite flows must not leak whether a target email exists beyond the current intended behavior.

## Audit Expectations

Current and future admin actions should have audit records where practical:

- login
- user invite/delete/reset
- classification correction
- rule approval/rejection/dismissal
- training pipeline run
- classifier training
- prompt version update
- app update
- future model promotion/rollback
- future external AI usage mode changes

## Risk Classes

Treat these conservatively:

- Billing disputes
- Chargebacks
- Refund requests
- Credit card authorization
- ADA/accessibility
- Medical issues
- Legal threats
- Discrimination complaints
- VIP/consortia bookings
- Same-day arrivals
- Group blocks
- Reputation/social review escalation
- Security or safety language

These should be surfaced for human review rather than hidden by confidence scores.

## Future Privacy Modes

Planned modes:

- No external AI.
- External AI only after manual approval.
- External AI allowed for low-risk emails.
- External AI allowed.

Until a UI setting exists, preserve the current code-level routing rules and conservative fallbacks.
