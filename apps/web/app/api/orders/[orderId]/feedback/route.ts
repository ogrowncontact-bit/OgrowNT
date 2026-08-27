import { NextRequest, NextResponse } from "next/server";
import { prisma, type PurchaseFeedbackReason } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { track } from "@/lib/analytics";

const VALID_REASONS: PurchaseFeedbackReason[] = [
  "curiosity",
  "free_result_accurate",
  "wanted_more_detail",
  "preview_convinced",
  "price_reasonable",
  "other",
];

/**
 * FASE 33 §PURCHASE FEEDBACK — "What made you decide to unlock your
 * report?", optional, asked once right after checkout succeeds. Ownership-
 * checked the same way report feedback/PDF download are.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  const anonymousSessionId = await readAnonymousSessionId();
  const accessUserId = await readAccessUserId();
  if (!anonymousSessionId && !accessUserId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const { orderId } = await params;
  const body = await request.json().catch(() => null);
  const reason = body?.reason as string | undefined;
  const otherText = (body?.otherText as string | undefined)?.trim().slice(0, 2000) || undefined;
  if (!reason || !VALID_REASONS.includes(reason as PurchaseFeedbackReason)) {
    return NextResponse.json({ error: "A valid reason is required" }, { status: 400 });
  }

  const order = await prisma.order.findUnique({
    where: { id: orderId },
    include: { assessmentSession: { include: { anonymousSession: true } } },
  });
  if (!order) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const ownsViaCurrentSession = anonymousSessionId !== null && order.assessmentSession.anonymousSessionId === anonymousSessionId;
  const ownsViaMagicLink = accessUserId !== null && order.assessmentSession.anonymousSession.userId === accessUserId;
  if (!ownsViaCurrentSession && !ownsViaMagicLink) return NextResponse.json({ error: "Not found" }, { status: 404 });

  await prisma.purchaseFeedback.upsert({
    where: { orderId },
    update: { reason: reason as PurchaseFeedbackReason, otherText },
    create: { orderId, reason: reason as PurchaseFeedbackReason, otherText },
  });

  await track({
    anonymousSessionId: order.assessmentSession.anonymousSessionId,
    eventName: "purchase_feedback_submitted",
    assessmentId: order.assessmentSession.assessmentId,
    properties: { reason },
  });

  return NextResponse.json({ ok: true });
}
