import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

/**
 * Fired client-side the moment a question first renders — question_viewed
 * per the adaptive engine spec's analytics requirements. Best-effort: a
 * failed beacon must never block the assessment flow. Only ever sends the
 * questionKey, never the answer.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ ok: true });

  const body = await request.json().catch(() => null);
  const questionKey = body?.questionKey as string | undefined;
  if (!questionKey) return NextResponse.json({ error: "questionKey is required" }, { status: 400 });

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) return NextResponse.json({ ok: true });

  await track({
    anonymousSessionId,
    eventName: "question_viewed",
    assessmentId: session.assessmentId,
    properties: { questionKey },
  });

  return NextResponse.json({ ok: true });
}
