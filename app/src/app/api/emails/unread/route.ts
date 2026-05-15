import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  const emails = await prisma.emailMessage.findMany({
    where: { isRead: false },
    orderBy: { receivedDateTime: "desc" },
    take: 100,
    include: {
      classifications: {
        orderBy: { createdAt: "desc" },
        take: 1
      }
    }
  });

  return NextResponse.json({ emails });
}
