import { prisma } from "@inner/db";
import { track } from "./analytics";

/**
 * Detects assessment sessions nobody is coming back to and closes them out —
 * the adaptive engine spec's assessment_abandoned event, which nothing
 * previously emitted (question_answered/assessment_completed already
 * existed, but there was no signal for "started and just... stopped").
 *
 * Meant to be invoked periodically, same shape as runReengagementBatch in
 * lib/reengagement.ts — see app/api/admin/jobs/abandonment/route.ts for the
 * scheduler wiring. Never touches sessions that are still plausibly active.
 */

const INACTIVITY_THRESHOLD_MS = 2 * 60 * 60 * 1000; // 2h with no activity — assessments take minutes, not hours
// Bounds the initial scan to sessions that could plausibly have crossed the
// inactivity threshold, so this never table-scans years of old completed data.
const SCAN_WINDOW_MS = 14 * 24 * 60 * 60 * 1000; // 14 days

export interface AbandonmentRunResult {
  abandoned: number;
  stillActive: number;
}

export async function detectAbandonedSessions(now: Date = new Date()): Promise<AbandonmentRunResult> {
  const cutoff = new Date(now.getTime() - INACTIVITY_THRESHOLD_MS);
  const scanFloor = new Date(now.getTime() - SCAN_WINDOW_MS);

  const candidates = await prisma.assessmentSession.findMany({
    where: { status: "in_progress", startedAt: { gte: scanFloor, lt: cutoff } },
  });

  let abandoned = 0;
  let stillActive = 0;

  for (const session of candidates) {
    const [lastResponse, lastOpenResponse] = await Promise.all([
      prisma.response.findFirst({ where: { assessmentSessionId: session.id }, orderBy: { answeredAt: "desc" } }),
      prisma.openResponse.findFirst({ where: { assessmentSessionId: session.id }, orderBy: { createdAt: "desc" } }),
    ]);

    const lastActivityAt = [session.startedAt, lastResponse?.answeredAt, lastOpenResponse?.createdAt]
      .filter((d): d is Date => !!d)
      .reduce((latest, d) => (d > latest ? d : latest), session.startedAt);

    if (lastActivityAt >= cutoff) {
      stillActive++;
      continue;
    }

    await prisma.assessmentSession.update({ where: { id: session.id }, data: { status: "abandoned" } });

    // Only the count of questions answered — never raw answers — per the
    // adaptive engine spec's analytics constraint.
    await track({
      anonymousSessionId: session.anonymousSessionId,
      eventName: "assessment_abandoned",
      assessmentId: session.assessmentId,
      properties: { questionsAnswered: session.questionCount },
    });
    abandoned++;
  }

  return { abandoned, stillActive };
}
