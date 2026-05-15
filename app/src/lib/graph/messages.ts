import { graphRequest, mailboxPath } from "@/lib/graph/client";

export type GraphRecipient = {
  emailAddress?: {
    name?: string | null;
    address?: string | null;
  };
};

export type GraphAttachment = {
  id?: string;
  name?: string;
  contentType?: string;
  size?: number;
};

export type GraphMessage = {
  id: string;
  internetMessageId?: string | null;
  conversationId?: string | null;
  subject?: string | null;
  bodyPreview?: string | null;
  body?: { contentType?: string; content?: string | null } | null;
  from?: GraphRecipient | null;
  sender?: GraphRecipient | null;
  toRecipients?: GraphRecipient[];
  ccRecipients?: GraphRecipient[];
  receivedDateTime?: string;
  isRead?: boolean;
  flag?: { flagStatus?: string | null } | null;
  categories?: string[];
  hasAttachments?: boolean;
  attachments?: GraphAttachment[];
};

type GraphListResponse<T> = {
  value: T[];
  "@odata.nextLink"?: string;
};

const selectFields = [
  "id",
  "internetMessageId",
  "conversationId",
  "subject",
  "bodyPreview",
  "body",
  "from",
  "sender",
  "toRecipients",
  "ccRecipients",
  "receivedDateTime",
  "isRead",
  "flag",
  "categories",
  "hasAttachments"
].join(",");

export async function getUnreadMessages(limit = 25) {
  const params = new URLSearchParams({
    "$filter": "isRead eq false",
    "$orderby": "receivedDateTime desc",
    "$top": String(limit),
    "$select": selectFields,
    "$expand": "attachments($select=id,name,contentType,size)"
  });

  const response = await graphRequest<GraphListResponse<GraphMessage>>(
    mailboxPath(`/mailFolders/inbox/messages?${params.toString()}`)
  );

  return response.value;
}

export function normalizeRecipients(recipients: GraphRecipient[] = []) {
  return recipients.map((recipient) => ({
    name: recipient.emailAddress?.name ?? null,
    email: recipient.emailAddress?.address ?? null
  }));
}

export function normalizeAttachments(attachments: GraphAttachment[] = []) {
  return attachments.map((attachment) => ({
    id: attachment.id ?? null,
    name: attachment.name ?? null,
    contentType: attachment.contentType ?? null,
    size: attachment.size ?? null
  }));
}

export function getSender(message: GraphMessage) {
  const sender = message.from?.emailAddress ?? message.sender?.emailAddress;
  return {
    name: sender?.name ?? null,
    email: sender?.address ?? "unknown@example.com"
  };
}
