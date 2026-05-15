import { BusinessCategory, PriorityLevel, ProcessingStatus } from "@prisma/client";
import { prisma } from "@/lib/db";
import { env } from "@/lib/env";
import { classifyReservationsEmail } from "@/lib/ai/classifier";
import { applyOutlookCategories, ensureDefaultOutlookCategories, flagMessage } from "@/lib/graph/categories";
import { getSender, getUnreadMessages, normalizeAttachments, normalizeRecipients } from "@/lib/graph/messages";
import { redactSensitivePaymentData } from "@/lib/security/redact";
import {
  CATEGORY_TO_ENUM,
  outlookCategoriesForClassification,
  PRIORITY_TO_ENUM
} from "@/lib/triage/taxonomy";

export async function processUnreadMessages(limit = 25) {
  const mailbox = await prisma.mailbox.upsert({
    where: { emailAddress: env.MICROSOFT_SHARED_MAILBOX },
    update: {},
    create: {
      emailAddress: env.MICROSOFT_SHARED_MAILBOX,
      displayName: "Waldorf Astoria Reservations"
    }
  });

  const messages = await getUnreadMessages(limit);
  if (!env.TRIAGE_DRY_RUN) {
    await ensureDefaultOutlookCategories();
  }

  const results = [];

  for (const message of messages) {
    const sender = getSender(message);
    const toRecipients = normalizeRecipients(message.toRecipients);
    const ccRecipients = normalizeRecipients(message.ccRecipients);
    const rawBody = message.body?.content ?? message.bodyPreview ?? "";
    const redacted = redactSensitivePaymentData(rawBody);
    const attachments = normalizeAttachments(message.attachments);

    const email = await prisma.emailMessage.upsert({
      where: {
        mailboxId_graphMessageId: {
          mailboxId: mailbox.id,
          graphMessageId: message.id
        }
      },
      update: {
        subject: message.subject ?? "",
        senderEmail: sender.email,
        senderName: sender.name,
        toRecipients,
        ccRecipients,
        bodyPreview: message.bodyPreview,
        sanitizedBody: redacted.text,
        hasAttachments: Boolean(message.hasAttachments),
        attachments,
        outlookCategories: message.categories ?? [],
        isRead: Boolean(message.isRead),
        isFlagged: message.flag?.flagStatus === "flagged",
        status: ProcessingStatus.FETCHED
      },
      create: {
        mailboxId: mailbox.id,
        graphMessageId: message.id,
        internetMessageId: message.internetMessageId,
        conversationId: message.conversationId,
        subject: message.subject ?? "",
        senderEmail: sender.email,
        senderName: sender.name,
        toRecipients,
        ccRecipients,
        receivedDateTime: message.receivedDateTime ? new Date(message.receivedDateTime) : new Date(),
        bodyPreview: message.bodyPreview,
        sanitizedBody: redacted.text,
        hasAttachments: Boolean(message.hasAttachments),
        attachments,
        outlookCategories: message.categories ?? [],
        isRead: Boolean(message.isRead),
        isFlagged: message.flag?.flagStatus === "flagged"
      }
    });

    const { classification, triggerEvidence } = await classifyReservationsEmail({
      subject: email.subject,
      senderEmail: email.senderEmail,
      senderName: email.senderName,
      toRecipients,
      ccRecipients,
      body: redacted.text,
      attachmentNames: attachments.map((attachment) => attachment.name ?? "").filter(Boolean)
    });

    const outlookCategories = outlookCategoriesForClassification(classification);
    const savedClassification = await prisma.classification.create({
      data: {
        emailMessageId: email.id,
        priority: PRIORITY_TO_ENUM[classification.priority] as PriorityLevel,
        category: CATEGORY_TO_ENUM[classification.category] as BusinessCategory,
        reason: classification.reason,
        recommendedDeadline: classification.recommended_deadline,
        suggestedCategoryColor: classification.suggested_category_color,
        outlookCategories,
        triggerEvidence,
        redactionSummary: redacted.summary,
        model: env.OPENAI_API_KEY ? env.OPENAI_MODEL : "heuristic-fallback",
        promptVersion: "reservations-triage-v1",
        rawModelOutput: classification
      }
    });

    let actionStatus = "dry_run";
    let actionError: string | null = null;

    if (!env.TRIAGE_DRY_RUN) {
      try {
        if (outlookCategories.length) {
          await applyOutlookCategories(message.id, [...new Set([...(message.categories ?? []), ...outlookCategories])]);
        }
        if (classification.priority === "Critical" || classification.priority === "High") {
          await flagMessage(message.id);
        }
        actionStatus = "applied";
      } catch (error) {
        actionStatus = "failed";
        actionError = error instanceof Error ? error.message : String(error);
      }
    }

    await prisma.actionLog.create({
      data: {
        emailMessageId: email.id,
        action: "classify_and_apply_outlook_categories",
        status: actionStatus,
        dryRun: env.TRIAGE_DRY_RUN,
        error: actionError,
        details: {
          classificationId: savedClassification.id,
          outlookCategories
        }
      }
    });

    await prisma.emailMessage.update({
      where: { id: email.id },
      data: {
        status: actionStatus === "failed" ? ProcessingStatus.FAILED : env.TRIAGE_DRY_RUN ? ProcessingStatus.CLASSIFIED : ProcessingStatus.APPLIED
      }
    });

    results.push({
      emailId: email.id,
      graphMessageId: message.id,
      subject: email.subject,
      classification,
      outlookCategories,
      dryRun: env.TRIAGE_DRY_RUN,
      actionStatus
    });
  }

  return results;
}
