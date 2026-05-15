import { z } from "zod";

const envSchema = z.object({
  DATABASE_URL: z.string().min(1),
  MICROSOFT_TENANT_ID: z.string().optional().default(""),
  MICROSOFT_CLIENT_ID: z.string().optional().default(""),
  MICROSOFT_CLIENT_SECRET: z.string().optional().default(""),
  MICROSOFT_SHARED_MAILBOX: z.string().email().default("Reservations@waldorfastoria.com"),
  OPENAI_API_KEY: z.string().optional().default(""),
  OPENAI_MODEL: z.string().default("gpt-4.1-mini"),
  TRIAGE_DRY_RUN: z
    .string()
    .default("true")
    .transform((value) => value.toLowerCase() !== "false"),
  NEXT_PUBLIC_APP_NAME: z.string().default("Waldorf Reservations Triage")
});

export const env = envSchema.parse(process.env);

export function assertGraphConfigured() {
  const missing = [
    ["MICROSOFT_TENANT_ID", env.MICROSOFT_TENANT_ID],
    ["MICROSOFT_CLIENT_ID", env.MICROSOFT_CLIENT_ID],
    ["MICROSOFT_CLIENT_SECRET", env.MICROSOFT_CLIENT_SECRET]
  ].filter(([, value]) => !value);

  if (missing.length) {
    throw new Error(`Microsoft Graph is not configured: ${missing.map(([key]) => key).join(", ")}`);
  }
}
