import { NextResponse } from "next/server";
import { processUnreadMessages } from "@/lib/sync/process-unread";

export async function POST(request: Request) {
  try {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") ?? 25);
    const results = await processUnreadMessages(limit);

    const accept = request.headers.get("accept") ?? "";
    if (accept.includes("text/html")) {
      return NextResponse.redirect(new URL("/", request.url), { status: 303 });
    }

    return NextResponse.json({ processed: results.length, results });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
