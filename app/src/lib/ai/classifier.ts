import { z } from "zod";
import { env } from "@/lib/env";
import { BUSINESS_CATEGORIES, PRIORITY_LEVELS } from "@/lib/triage/taxonomy";
import { detectCriticalTriggers, shouldForceCritical } from "@/lib/triage/triggers";

export const classificationSchema = z.object({
  priority: z.enum(PRIORITY_LEVELS),
  category: z.enum(BUSINESS_CATEGORIES),
  reason: z.string().min(5),
  recommended_deadline: z.string().min(3),
  suggested_category_color: z.enum(["Red", "Orange", "Blue", "Green", "Purple", "Gray"])
});

export type ClassificationOutput = z.infer<typeof classificationSchema>;

export async function classifyReservationsEmail(input: {
  subject: string;
  senderEmail: string;
  senderName?: string | null;
  toRecipients: Array<{ email?: string; name?: string }>;
  ccRecipients: Array<{ email?: string; name?: string }>;
  body: string;
  attachmentNames: string[];
}) {
  const triggerEvidence = detectCriticalTriggers(input);
  const aiResult = await callOpenAiClassifier(input);

  const classification =
    shouldForceCritical(triggerEvidence) && aiResult.priority !== "Critical"
      ? {
          ...aiResult,
          priority: "Critical" as const,
          reason: `${aiResult.reason} Critical trigger detected: ${triggerEvidence.matchedTerms.join(", ")}.`
        }
      : aiResult;

  return { classification, triggerEvidence };
}

async function callOpenAiClassifier(input: {
  subject: string;
  senderEmail: string;
  senderName?: string | null;
  toRecipients: Array<{ email?: string; name?: string }>;
  ccRecipients: Array<{ email?: string; name?: string }>;
  body: string;
  attachmentNames: string[];
}): Promise<ClassificationOutput> {
  if (!env.OPENAI_API_KEY) {
    return heuristicFallback(input);
  }

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: env.OPENAI_MODEL,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content: [
            "You classify emails for the Reservations department at Waldorf Astoria New York.",
            "Use only the allowed priority levels and business categories.",
            "Return compact JSON with priority, category, reason, recommended_deadline, and suggested_category_color.",
            `Allowed priorities: ${PRIORITY_LEVELS.join(", ")}.`,
            `Allowed categories: ${BUSINESS_CATEGORIES.join(", ")}.`
          ].join("\n")
        },
        {
          role: "user",
          content: JSON.stringify({
            subject: input.subject,
            sender: { email: input.senderEmail, name: input.senderName },
            to: input.toRecipients,
            cc: input.ccRecipients,
            attachmentNames: input.attachmentNames,
            body: input.body.slice(0, 6000)
          })
        }
      ],
      temperature: 0.1
    })
  });

  if (!response.ok) {
    throw new Error(`OpenAI classification failed: ${response.status} ${await response.text()}`);
  }

  const json = await response.json();
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("OpenAI classification returned no content");

  return classificationSchema.parse(JSON.parse(content));
}

function heuristicFallback(input: { subject: string; body: string }): ClassificationOutput {
  const text = `${input.subject}\n${input.body}`.toLowerCase();

  if (text.includes("sertifi") || text.includes("credit card") || text.includes("cca")) {
    return {
      priority: "Critical",
      category: "Payment Needed / CCA / Sertifi",
      reason: "Payment authorization language indicates the reservation may require action before confirmation.",
      recommended_deadline: "Within 1 hour",
      suggested_category_color: "Green"
    };
  }

  if (text.includes("vip") || text.includes("owner")) {
    return {
      priority: "Critical",
      category: "VIP / Owner / Celebrity",
      reason: "VIP or owner-level language requires immediate reservations review.",
      recommended_deadline: "Within 1 hour",
      suggested_category_color: "Purple"
    };
  }

  return {
    priority: "Normal",
    category: "Agent Quote Request",
    reason: "The message appears to be a standard reservations inquiry.",
    recommended_deadline: "Same business day",
    suggested_category_color: "Blue"
  };
}
