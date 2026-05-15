import { graphRequest, mailboxPath } from "@/lib/graph/client";
import { OUTLOOK_CATEGORY_MAP } from "@/lib/triage/taxonomy";

type OutlookCategory = {
  id?: string;
  displayName?: string;
  color?: string;
};

export async function ensureDefaultOutlookCategories() {
  const existing = await graphRequest<{ value: OutlookCategory[] }>(
    mailboxPath("/outlook/masterCategories")
  );
  const existingNames = new Set(existing.value.map((category) => category.displayName));

  const required = Object.values(OUTLOOK_CATEGORY_MAP);
  const created: OutlookCategory[] = [];

  for (const category of required) {
    if (existingNames.has(category.name)) continue;
    const result = await graphRequest<OutlookCategory>(mailboxPath("/outlook/masterCategories"), {
      method: "POST",
      body: JSON.stringify({
        displayName: category.name,
        color: category.color
      })
    });
    created.push(result);
  }

  return { existing: existing.value, created };
}

export async function applyOutlookCategories(messageId: string, categories: string[]) {
  return graphRequest(mailboxPath(`/messages/${encodeURIComponent(messageId)}`), {
    method: "PATCH",
    body: JSON.stringify({ categories })
  });
}

export async function flagMessage(messageId: string) {
  return graphRequest(mailboxPath(`/messages/${encodeURIComponent(messageId)}`), {
    method: "PATCH",
    body: JSON.stringify({
      flag: {
        flagStatus: "flagged"
      }
    })
  });
}
