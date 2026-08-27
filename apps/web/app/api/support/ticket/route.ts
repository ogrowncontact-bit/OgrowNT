import { NextRequest, NextResponse } from "next/server";
import { prisma, type SupportTicketCategory } from "@inner/db";
import { checkRateLimit } from "@/lib/security/rateLimit";

const VALID_CATEGORIES: SupportTicketCategory[] = ["payment", "report", "email", "technical", "content"];

/** FASE 33 §SUPPORT — a lightweight issue-report queue, distinct from the existing "resend my report" flow. No answer content is ever collected here. */
export async function POST(request: NextRequest) {
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const rate = await checkRateLimit("support_ticket", ip, { maxAttempts: 5, windowMs: 60 * 60 * 1000 });
  if (!rate.allowed) return NextResponse.json({ error: "Too many requests — please try again later" }, { status: 429 });

  const body = await request.json().catch(() => null);
  const category = body?.category as string | undefined;
  const email = (body?.email as string | undefined)?.trim().toLowerCase();
  const message = (body?.message as string | undefined)?.trim().slice(0, 4000);

  if (!category || !VALID_CATEGORIES.includes(category as SupportTicketCategory)) {
    return NextResponse.json({ error: "A valid category is required" }, { status: 400 });
  }
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: "A valid email is required" }, { status: 400 });
  }
  if (!message) {
    return NextResponse.json({ error: "A message is required" }, { status: 400 });
  }

  await prisma.supportTicket.create({
    data: { category: category as SupportTicketCategory, email, message },
  });

  return NextResponse.json({ ok: true });
}
