import { prisma } from "@inner/db";

export interface SegmentRow {
  key: string;
  label: string;
  size: number;
}

export interface PerAssessmentSegment {
  slug: string;
  name: string;
  completed: number;
  purchased: number;
}

/**
 * Derived, behavior-based segments only — never built from assessment
 * answers, profile results, or report content (see the spec's own
 * "keep marketing segmentation behavior-based" guidance). Every segment
 * here is computed on read, not stored — cheap enough at this data volume
 * and avoids a second source of truth that could drift from the real
 * Order/AssessmentSession/MarketingConsent rows.
 */
export async function getGlobalSegments(): Promise<SegmentRow[]> {
  const [multiAssessment, multiPurchase, optedIn, noPurchase, totalUsers, returning] = await Promise.all([
    // 2+ distinct completed assessments under the same user
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT count(*) FROM (
        SELECT u.id
        FROM identity."User" u
        JOIN identity."AnonymousSession" a ON a."userId" = u.id
        JOIN runtime."AssessmentSession" s ON s."anonymousSessionId" = a.id AND s.status = 'completed'
        GROUP BY u.id
        HAVING count(DISTINCT s."assessmentId") >= 2
      ) t
    `,
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT count(*) FROM (
        SELECT o."userId" FROM commerce."Order" o WHERE o.status = 'paid' GROUP BY o."userId" HAVING count(*) >= 2
      ) t
    `,
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT count(DISTINCT mc."userId") FROM marketing."MarketingConsent" mc
      WHERE mc.consent = true
      AND mc."consentTimestamp" = (
        SELECT max(mc2."consentTimestamp") FROM marketing."MarketingConsent" mc2 WHERE mc2."userId" = mc."userId"
      )
    `,
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT count(*) FROM identity."User" u
      WHERE NOT EXISTS (SELECT 1 FROM commerce."Order" o WHERE o."userId" = u.id AND o.status = 'paid')
    `,
    prisma.user.count(),
    // At least one anonymous session with a real gap between first and last seen — a same-cookie return visit, not just multi-tab activity in one sitting.
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT count(DISTINCT a."userId") FROM identity."AnonymousSession" a
      WHERE a."userId" IS NOT NULL AND a."lastSeenAt" > a."createdAt" + interval '1 day'
    `,
  ]);

  return [
    { key: "MULTI_ASSESSMENT_USER", label: "Completed 2+ assessments", size: Number(multiAssessment[0]?.count ?? 0) },
    { key: "MULTI_PURCHASE_USER", label: "2+ paid purchases", size: Number(multiPurchase[0]?.count ?? 0) },
    { key: "MARKETING_OPTED_IN", label: "Opted into marketing (latest consent)", size: Number(optedIn[0]?.count ?? 0) },
    { key: "NO_PURCHASE", label: "Never purchased", size: Number(noPurchase[0]?.count ?? 0) },
    { key: "RETURNING_USER", label: "Returned after 24h+", size: Number(returning[0]?.count ?? 0) },
    { key: "TOTAL_USERS", label: "Total identified users", size: totalUsers },
  ];
}

/** Per-assessment COMPLETED / PURCHASED counts — the "LOVE_COMPLETED" style segments from the spec, one row per real experience. */
export async function getPerAssessmentSegments(): Promise<PerAssessmentSegment[]> {
  const assessments = await prisma.assessment.findMany({
    select: {
      slug: true,
      name: true,
      _count: { select: { assessmentSessions: { where: { status: "completed" } } } },
    },
    orderBy: { name: "asc" },
  });

  const paidCounts = await prisma.order.groupBy({ by: ["priceId"], where: { status: "paid" }, _count: { _all: true } });
  const prices = await prisma.price.findMany({ where: { id: { in: paidCounts.map((p) => p.priceId) } }, select: { id: true, assessmentId: true } });
  const priceToAssessment = new Map(prices.map((p) => [p.id, p.assessmentId]));
  const paidByAssessmentId = new Map<string, number>();
  for (const p of paidCounts) {
    const assessmentId = priceToAssessment.get(p.priceId);
    if (!assessmentId) continue;
    paidByAssessmentId.set(assessmentId, (paidByAssessmentId.get(assessmentId) ?? 0) + p._count._all);
  }
  const idsBySlug = await prisma.assessment.findMany({ select: { id: true, slug: true } });
  const slugToId = new Map(idsBySlug.map((a) => [a.slug, a.id]));

  return assessments.map((a) => ({
    slug: a.slug,
    name: a.name,
    completed: a._count.assessmentSessions,
    purchased: paidByAssessmentId.get(slugToId.get(a.slug) ?? "") ?? 0,
  }));
}
