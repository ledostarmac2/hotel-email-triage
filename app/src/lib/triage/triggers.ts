export type TriggerEvidence = {
  arrivalSoon: boolean;
  vipOrOwner: boolean;
  urgentLanguage: boolean;
  paymentRequired: boolean;
  highValueComplaint: boolean;
  executiveCopied: boolean;
  matchedTerms: string[];
};

const urgentTerms = ["urgent", "asap", "immediate", "time sensitive", "need today", "rush"];
const paymentTerms = ["payment required", "credit card authorization", "cca", "sertifi", "deposit", "guarantee the reservation", "secure the reservation"];
const vipTerms = ["vip 3", "vip3", "owner", "celebrity", "presidential suite", "diamond guest"];
const complaintTerms = ["complaint", "unacceptable", "escalate", "disappointed", "service failure", "manager"];
const executiveTerms = ["managing director", "sales director", "executive office", "general manager"];
const arrivalTerms = ["arrival today", "arriving today", "arrival tomorrow", "arriving tomorrow", "checks in today", "checks in tomorrow"];

export function detectCriticalTriggers(message: {
  subject: string;
  body: string;
  senderEmail?: string | null;
  ccRecipients?: Array<{ email?: string; name?: string }>;
}): TriggerEvidence {
  const haystack = [
    message.subject,
    message.body,
    message.senderEmail,
    ...(message.ccRecipients ?? []).flatMap((recipient) => [recipient.email, recipient.name])
  ]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();

  const matchedTerms = [
    ...findTerms(haystack, urgentTerms),
    ...findTerms(haystack, paymentTerms),
    ...findTerms(haystack, vipTerms),
    ...findTerms(haystack, complaintTerms),
    ...findTerms(haystack, executiveTerms),
    ...findTerms(haystack, arrivalTerms)
  ];

  return {
    arrivalSoon: findTerms(haystack, arrivalTerms).length > 0,
    vipOrOwner: findTerms(haystack, vipTerms).length > 0,
    urgentLanguage: findTerms(haystack, urgentTerms).length > 0,
    paymentRequired: findTerms(haystack, paymentTerms).length > 0,
    highValueComplaint: findTerms(haystack, complaintTerms).length > 0 && findTerms(haystack, [...vipTerms, "amex", "centurion", "virtuoso"]).length > 0,
    executiveCopied: findTerms(haystack, executiveTerms).length > 0,
    matchedTerms: [...new Set(matchedTerms)]
  };
}

export function shouldForceCritical(evidence: TriggerEvidence) {
  return (
    evidence.arrivalSoon ||
    evidence.vipOrOwner ||
    evidence.urgentLanguage ||
    evidence.paymentRequired ||
    evidence.highValueComplaint ||
    evidence.executiveCopied
  );
}

function findTerms(haystack: string, terms: string[]) {
  return terms.filter((term) => haystack.includes(term));
}
