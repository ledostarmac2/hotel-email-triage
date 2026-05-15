import { assertGraphConfigured, env } from "@/lib/env";

const graphRoot = "https://graph.microsoft.com/v1.0";

let cachedToken: { accessToken: string; expiresAt: number } | null = null;

export async function getGraphAccessToken() {
  assertGraphConfigured();

  if (cachedToken && cachedToken.expiresAt > Date.now() + 60_000) {
    return cachedToken.accessToken;
  }

  const tokenUrl = `https://login.microsoftonline.com/${env.MICROSOFT_TENANT_ID}/oauth2/v2.0/token`;
  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.MICROSOFT_CLIENT_ID,
      client_secret: env.MICROSOFT_CLIENT_SECRET,
      scope: "https://graph.microsoft.com/.default",
      grant_type: "client_credentials"
    })
  });

  if (!response.ok) {
    throw new Error(`Microsoft token request failed: ${response.status} ${await response.text()}`);
  }

  const payload = (await response.json()) as { access_token: string; expires_in: number };
  cachedToken = {
    accessToken: payload.access_token,
    expiresAt: Date.now() + payload.expires_in * 1000
  };

  return cachedToken.accessToken;
}

export async function graphRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await getGraphAccessToken();
  const response = await fetch(`${graphRoot}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      Prefer: 'IdType="ImmutableId"',
      ...(init.headers ?? {})
    }
  });

  if (!response.ok) {
    throw new Error(`Microsoft Graph request failed: ${response.status} ${await response.text()}`);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function mailboxPath(path: string, mailbox = env.MICROSOFT_SHARED_MAILBOX) {
  return `/users/${encodeURIComponent(mailbox)}${path.startsWith("/") ? path : `/${path}`}`;
}
