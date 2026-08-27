import { prisma, type FeedbackRating } from "@inner/db";

/**
 * FASE 33 §SOFT LAUNCH DASHBOARD — LOVE-scoped rollups for /admin/launch/love.
 * Deliberately composes the same underlying readers used elsewhere in admin
 * (funnel/AI/feedback) rather than re-deriving them, and is honest about
 * what "technical errors" means here: there's no dedicated error-log model
 * in this stack, so it's assembled from the failure signals that already
 * exist (failed report generation, failed AI calls, failed report emails).
 */

export async function getLoveAssessment(): Promise<{ id: string; name: string; releaseVersion: string } | null> {
  return prisma.assessment.findUnique({ where: { slug: "love" }, select: { id: true, name: true, releaseVersion: true } });
}

export interface LoveTrafficStats {
  totalVisitors: number;
  deviceBreakdown: { device: string; count: number }[];
}

export async function getLoveTrafficStats(assessmentId: string): Promise<LoveTrafficStats> {
  // Excludes FASE 31's QA-simulation-tagged sessions — those skip analytics
  // events (skipAnalytics: true) but still create real AssessmentSession
  // rows, which would otherwise inflate this DB-row-based count even though
  // the Event-based funnel below correctly excludes them.
  const sessions = await prisma.assessmentSession.findMany({
    where: { assessmentId, anonymousSession: { utmSource: { not: "qa_simulation" } } },
    select: { anonymousSession: { select: { deviceType: true } } },
    distinct: ["anonymousSessionId"],
  });
  const counts = new Map<string, number>();
  for (const s of sessions) {
    const device = s.anonymousSession.deviceType ?? "unknown";
    counts.set(device, (counts.get(device) ?? 0) + 1);
  }
  return {
    totalVisitors: sessions.length,
    deviceBreakdown: [...counts.entries()].map(([device, count]) => ({ device, count })).sort((a, b) => b.count - a.count),
  };
}

export interface LoveReportPipelineStats {
  started: number;
  ready: number;
  failed: number;
  delivered: number;
  emailFailed: number;
}

export async function getLoveReportPipelineStats(assessmentId: string): Promise<LoveReportPipelineStats> {
  const [started, ready, failed, delivered, emailFailed] = await Promise.all([
    prisma.event.count({ where: { assessmentId, eventName: "report_generation_started" } }),
    prisma.event.count({ where: { assessmentId, eventName: "report_generated" } }),
    prisma.event.count({ where: { assessmentId, eventName: "report_generation_failed" } }),
    prisma.event.count({ where: { assessmentId, eventName: "report_delivered" } }),
    prisma.event.count({ where: { assessmentId, eventName: "report_email_failed" } }),
  ]);
  return { started, ready, failed, delivered, emailFailed };
}

const RATING_SCORE: Record<FeedbackRating, number> = {
  very_accurate: 5,
  mostly_accurate: 4,
  somewhat_accurate: 3,
  not_very_accurate: 2,
  not_accurate: 1,
};

export interface LoveDailySummary {
  visitors: number;
  starts: number;
  completions: number;
  purchases: number;
  revenueCents: number;
  conversionPct: number;
  avgRating: number | null;
  mostCommonRating: string | null;
  topAbandonmentReason: string | null;
  technicalErrors: number;
}

export async function getLoveDailySummary(assessmentId: string): Promise<LoveDailySummary> {
  const startOfToday = new Date();
  startOfToday.setUTCHours(0, 0, 0, 0);
  const occurredAt = { gte: startOfToday };

  const [visitors, starts, completions, purchases, paidToday, ratings, abandonmentReasons, reportFailures, aiFailures, emailFailures] =
    await Promise.all([
      prisma.event.count({ where: { assessmentId, eventName: "landing_view", occurredAt } }),
      prisma.event.count({ where: { assessmentId, eventName: "assessment_started", occurredAt } }),
      prisma.event.count({ where: { assessmentId, eventName: "assessment_completed", occurredAt } }),
      prisma.event.count({ where: { assessmentId, eventName: "payment_completed", occurredAt } }),
      prisma.order.aggregate({ where: { status: "paid", paidAt: occurredAt, assessmentSession: { assessmentId } }, _sum: { amountCents: true } }),
      prisma.reportFeedback.findMany({ where: { createdAt: occurredAt, report: { assessmentSession: { assessmentId } } }, select: { rating: true } }),
      prisma.abandonmentFeedback.groupBy({
        by: ["reason"],
        where: { createdAt: occurredAt, assessmentSession: { assessmentId } },
        _count: { _all: true },
        orderBy: { _count: { reason: "desc" } },
      }),
      prisma.event.count({ where: { assessmentId, eventName: "report_generation_failed", occurredAt } }),
      prisma.aiCallLog.count({ where: { ok: false, occurredAt } }),
      prisma.event.count({ where: { assessmentId, eventName: "report_email_failed", occurredAt } }),
    ]);

  const avgRating = ratings.length > 0 ? ratings.reduce((sum, r) => sum + RATING_SCORE[r.rating], 0) / ratings.length : null;
  const ratingCounts = new Map<FeedbackRating, number>();
  for (const r of ratings) ratingCounts.set(r.rating, (ratingCounts.get(r.rating) ?? 0) + 1);
  const mostCommonRating = [...ratingCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

  return {
    visitors,
    starts,
    completions,
    purchases,
    revenueCents: paidToday._sum.amountCents ?? 0,
    conversionPct: visitors > 0 ? Math.round((purchases / visitors) * 1000) / 10 : 0,
    avgRating: avgRating !== null ? Math.round(avgRating * 10) / 10 : null,
    mostCommonRating,
    topAbandonmentReason: abandonmentReasons[0]?.reason ?? null,
    // AI failures aren't scoped to one assessment (AiCallLog has no
    // assessmentId), so this is a platform-wide count on days LOVE is the
    // only real product taking traffic — honestly labelled as such in the UI.
    technicalErrors: reportFailures + aiFailures + emailFailures,
  };
}

export interface LoveAbandonmentReasonRow {
  reason: string;
  count: number;
}

export async function getLoveAbandonmentReasons(assessmentId: string): Promise<LoveAbandonmentReasonRow[]> {
  const grouped = await prisma.abandonmentFeedback.groupBy({
    by: ["reason"],
    where: { assessmentSession: { assessmentId } },
    _count: { _all: true },
    orderBy: { _count: { reason: "desc" } },
  });
  return grouped.map((g) => ({ reason: g.reason, count: g._count._all }));
}

export interface LovePurchaseReasonRow {
  reason: string;
  count: number;
}

export async function getLovePurchaseReasons(assessmentId: string): Promise<LovePurchaseReasonRow[]> {
  const grouped = await prisma.purchaseFeedback.groupBy({
    by: ["reason"],
    where: { order: { assessmentSession: { assessmentId } } },
    _count: { _all: true },
    orderBy: { _count: { reason: "desc" } },
  });
  return grouped.map((g) => ({ reason: g.reason, count: g._count._all }));
}
