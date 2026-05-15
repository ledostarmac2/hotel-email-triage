import { NextResponse } from "next/server";
import { env } from "@/lib/env";

export function GET() {
  return NextResponse.json({
    ok: true,
    app: env.NEXT_PUBLIC_APP_NAME,
    mailbox: env.MICROSOFT_SHARED_MAILBOX,
    dryRun: env.TRIAGE_DRY_RUN,
    graphConfigured: Boolean(env.MICROSOFT_TENANT_ID && env.MICROSOFT_CLIENT_ID && env.MICROSOFT_CLIENT_SECRET),
    aiConfigured: Boolean(env.OPENAI_API_KEY)
  });
}
