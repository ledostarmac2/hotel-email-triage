# Operations Guide

Last updated: 2026-05-18

## Purpose

ReplyRight helps hotel operators work a reservations inbox faster without losing human judgment.

It ranks email conversations, summarizes what needs attention, identifies the likely owner, flags risk, and can draft a suggested reply for review.

It does not send emails or modify Outlook.

## Daily Workflow

1. Launch ReplyRight.
2. Log in.
3. Click Refresh Inbox.
4. Work the queue from highest urgency to lowest.
5. Open a conversation and review the original messages.
6. Use the summary, required actions, owner, category, risk flags, and confidence as decision support.
7. If the classification is wrong, submit feedback.
8. Use AI Suggestion only when a drafted response would help.
9. Review and edit any AI text before using it outside ReplyRight.

## Queue Meaning

Urgency levels:

- `5`: immediate operational risk, same-day arrival, serious complaint, medical/legal/accessibility/payment blocker, or comparable escalation.
- `4`: high priority, near arrival, billing dispute, VIP/travel advisor issue, or strong complaint.
- `3`: normal operational action, usually same-week or clear task.
- `2`: low priority but actionable.
- `1`: FYI, acknowledgment, completed update, or low-action item.

Owner values:

- Front Desk
- Reservations
- Concierge
- Sales
- Housekeeping
- Engineering
- All Departments

Contact types:

- Internal
- Group contact
- Travel agency
- Direct guest

## Confidence

Confidence is a signal, not a guarantee.

High confidence means the app saw strong familiar patterns. Low confidence means the email should be reviewed carefully. Risk flags should override comfort with a high score; risky messages still need human judgment.

## When To Correct The App

Submit feedback when:

- Urgency is too high or too low.
- The owner is wrong.
- The category is wrong.
- Contact type is wrong.
- Summary misses the actual ask.
- Reply draft is not usable.
- The app missed a risk flag.
- The message is actually complete/no-action.

Corrections help future classification and training.

## High-Risk Emails

Handle these conservatively:

- Billing disputes
- Refund requests
- Chargebacks
- Credit card authorization issues
- ADA/accessibility requests
- Medical issues
- Legal threats
- Discrimination concerns
- VIP or travel program bookings
- Same-day arrivals
- Guest complaints or reputation/social review escalation
- Security or safety language

Do not rely solely on an AI draft for these. Review the full thread and follow hotel policy.

## AI Suggestion

AI Suggestion is for one selected email/conversation. It is not an automatic send flow.

Before using a draft:

- Read the original email.
- Verify facts, dates, names, room types, rates, and policy details.
- Remove promises the hotel cannot guarantee.
- Avoid committing to refunds, compensation, upgrades, early check-in, late checkout, billing exceptions, legal positions, or ADA commitments unless approved.
- Adjust tone for the guest, travel advisor, or internal colleague.

## Training And Feedback

The Admin training pipeline can export completed, redacted emails to Supabase as training examples. Human-reviewed examples can train the local classifier.

Operators should focus on accurate feedback. Admins should review labels before classifier training.

## What Not To Do

- Do not assume ReplyRight has full reservation-system context.
- Do not send an AI draft without review.
- Do not paste raw secrets or credentials into feedback.
- Do not treat a low-risk classification as proof that there is no risk.
- Do not use ReplyRight to modify Outlook messages; it is currently read-only.

## If Something Looks Wrong

1. Open the full conversation.
2. Check whether the latest message is a reply/acknowledgment or a new request.
3. Check arrival date and same-day implications.
4. Check for billing, accessibility, legal, medical, VIP, and complaint language.
5. Correct the classification with feedback.
6. Escalate manually through normal hotel channels when risk is present.
