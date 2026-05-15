export const PRIORITY_LEVELS = ["Critical", "High", "Normal", "Low"] as const;

export const BUSINESS_CATEGORIES = [
  "Arrival Today",
  "VIP / Owner / Celebrity",
  "FHR / Centurion",
  "Hilton for Luxury / Impresario",
  "Virtuoso",
  "Payment Needed / CCA / Sertifi",
  "Agent Quote Request",
  "Rate Match",
  "Waitlist",
  "Guest Complaint",
  "Folio Request",
  "Cancellation / Modification",
  "Internal / FYI",
  "Duplicate Follow-Up",
  "Low Priority"
] as const;

export const CATEGORY_TO_ENUM = {
  "Arrival Today": "ARRIVAL_TODAY",
  "VIP / Owner / Celebrity": "VIP_OWNER_CELEBRITY",
  "FHR / Centurion": "FHR_CENTURION",
  "Hilton for Luxury / Impresario": "HILTON_FOR_LUXURY_IMPRESARIO",
  Virtuoso: "VIRTUOSO",
  "Payment Needed / CCA / Sertifi": "PAYMENT_NEEDED_CCA_SERTIFI",
  "Agent Quote Request": "AGENT_QUOTE_REQUEST",
  "Rate Match": "RATE_MATCH",
  Waitlist: "WAITLIST",
  "Guest Complaint": "GUEST_COMPLAINT",
  "Folio Request": "FOLIO_REQUEST",
  "Cancellation / Modification": "CANCELLATION_MODIFICATION",
  "Internal / FYI": "INTERNAL_FYI",
  "Duplicate Follow-Up": "DUPLICATE_FOLLOW_UP",
  "Low Priority": "LOW_PRIORITY"
} as const;

export const PRIORITY_TO_ENUM = {
  Critical: "CRITICAL",
  High: "HIGH",
  Normal: "NORMAL",
  Low: "LOW"
} as const;

export const OUTLOOK_CATEGORY_MAP = {
  critical: { name: "Red - Critical", color: "preset0" },
  high: { name: "Orange - High Priority", color: "preset1" },
  salesQuote: { name: "Blue - Sales Quote", color: "preset5" },
  payment: { name: "Green - Payment Needed", color: "preset3" },
  vip: { name: "Purple - VIP", color: "preset6" },
  low: { name: "Gray - Low Priority", color: "preset9" }
} as const;

export function outlookCategoriesForClassification(input: {
  priority: string;
  category: string;
}) {
  const categories = new Set<string>();

  if (input.priority === "Critical") categories.add(OUTLOOK_CATEGORY_MAP.critical.name);
  if (input.priority === "High") categories.add(OUTLOOK_CATEGORY_MAP.high.name);
  if (input.category === "Agent Quote Request") categories.add(OUTLOOK_CATEGORY_MAP.salesQuote.name);
  if (input.category === "Payment Needed / CCA / Sertifi") categories.add(OUTLOOK_CATEGORY_MAP.payment.name);
  if (input.category === "VIP / Owner / Celebrity") categories.add(OUTLOOK_CATEGORY_MAP.vip.name);
  if (input.priority === "Low" || input.category === "Low Priority") categories.add(OUTLOOK_CATEGORY_MAP.low.name);

  if (categories.size === 0 && input.priority === "Normal") {
    return [];
  }

  return [...categories];
}
