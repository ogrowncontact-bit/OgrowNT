import { NextRequest, NextResponse } from "next/server";
import { prisma, type FeedbackRating } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { track } from "@/lib/analytics";

const VALID_RATINGS: FeedbackRating[] = ["very_accurate", "mostly_accurate", "somewhat_accurate", "not_very_accurate", "not_accurate"];

/**
 * FASE 32 §FEEDBACK — optional, never required to see or keep the report.
 * Ownership-checked the same way PDF download is: the report's own session
 * must belong to this browser's anonymous session or an authenticated
 * magic-link user. One submission per report (upsert, not accumulated).
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ reportId: string }> }) {
  const anonymousSessionId = await readAnonymousSessionId();
  const accessUserId = await readAccessUserId();
  if (!anonymousSessionId && !accessUserId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const { reportId } = await params;
  const body = await request.json().catch(() => null);
  const rating = body?.rating as string | undefined;
  const comment = (body?.comment as string | undefined)?.trim().slice(0, 2000) || undefined;
  if (!rating || !VALID_RATINGS.includes(rating as FeedbackRating)) {
    return NextResponse.json({ error: "A valid rating is required" }, { status: 400 });
  }

  const report = await prisma.report.findUnique({
    where: { id: reportId },
    include: { assessmentSession: { include: { anonymousSession: true } } },
  });
  if (!report) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const ownsViaCurrentSession = anonymousSessionId !== null && report.assessmentSession.anonymousSessionId === anonymousSessionId;
  const ownsViaMagicLink = accessUserId !== null && report.assessmentSession.anonymousSession.userId === accessUserId;
  if (!ownsViaCurrentSession && !ownsViaMagicLink) return NextResponse.json({ error: "Not found" }, { status: 404 });

  await prisma.reportFeedback.upsert({
    where: { reportId },
    update: { rating: rating as FeedbackRating, comment },
    create: { reportId, rating: rating as FeedbackRating, comment },
  });

  await track({
    anonymousSessionId: report.assessmentSession.anonymousSessionId,
    eventName: "report_feedback_submitted",
    assessmentId: report.assessmentSession.assessmentId,
    properties: { rating },
  });

  return NextResponse.json({ ok: true });
}
