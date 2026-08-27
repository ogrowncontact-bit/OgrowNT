import { NextRequest, NextResponse } from "next/server";
import { prisma, type AbandonmentFeedbackReason } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

const VALID_REASONS: AbandonmentFeedbackReason[] = [
  "too_expensive",
  "not_sure_useful",
  "wanted_to_think",
  "not_enough_info",
  "technical_problem",
  "other",
];

/**
 * FASE 33 §ABANDONMENT FEEDBACK — "What stopped you?", offered inline on the
 * paywall, never a popup/interruption, never mandatory. Only reachable by
 * the session's own anonymous session (no magic-link case — a session that
 * hasn't purchased has no order to have arrived via a magic link).
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const { id } = await params;
  const body = await request.json().catch(() => null);
  const reason = body?.reason as string | undefined;
  const otherText = (body?.otherText as string | undefined)?.trim().slice(0, 2000) || undefined;
  if (!reason || !VALID_REASONS.includes(reason as AbandonmentFeedbackReason)) {
    return NextResponse.json({ error: "A valid reason is required" }, { status: 400 });
  }

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  await prisma.abandonmentFeedback.upsert({
    where: { assessmentSessionId: id },
    update: { reason: reason as AbandonmentFeedbackReason, otherText },
    create: { assessmentSessionId: id, reason: reason as AbandonmentFeedbackReason, otherText },
  });

  await track({ anonymousSessionId, eventName: "abandonment_feedback_submitted", assessmentId: session.assessmentId, properties: { reason } });

  return NextResponse.json({ ok: true });
}
