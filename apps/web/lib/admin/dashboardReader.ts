import { prisma } from "@inner/db";

export interface DashboardOverview {
  totalAssessments: number;
  publishedAssessments: number;
  totalStartedSessions: number;
  totalCompletedSessions: number;
  totalPaidOrders: number;
  totalRevenueCents: number;
  completionToPaidConversionPct: number;
  pendingOrders: number;
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const [totalAssessments, publishedAssessments, totalStartedSessions, totalCompletedSessions, paidAgg, pendingOrders] = await Promise.all([
    prisma.assessment.count(),
    prisma.assessment.count({ where: { status: "published" } }),
    prisma.assessmentSession.count(),
    prisma.assessmentSession.count({ where: { status: "completed" } }),
    prisma.order.aggregate({ where: { status: "paid" }, _sum: { amountCents: true }, _count: { _all: true } }),
    // An order can sit "pending" if a webhook never lands (or a mock-payment click never completes) — worth an operator's attention if this creeps up.
    prisma.order.count({ where: { status: "pending" } }),
  ]);

  const totalPaidOrders = paidAgg._count._all;
  const totalRevenueCents = paidAgg._sum.amountCents ?? 0;

  return {
    totalAssessments,
    publishedAssessments,
    totalStartedSessions,
    totalCompletedSessions,
    totalPaidOrders,
    totalRevenueCents,
    completionToPaidConversionPct: totalCompletedSessions > 0 ? Math.round((totalPaidOrders / totalCompletedSessions) * 1000) / 10 : 0,
    pendingOrders,
  };
}

export interface TopAssessmentRow {
  slug: string;
  name: string;
  completions: number;
  paidOrders: number;
}

/** Ranked by completed sessions — the clearest "which experience actually works" signal we have without a heavier analytics pass. */
export async function getTopAssessments(limit = 5): Promise<TopAssessmentRow[]> {
  const assessments = await prisma.assessment.findMany({
    select: {
      slug: true,
      name: true,
      _count: { select: { assessmentSessions: { where: { status: "completed" } } } },
    },
  });

  const paidCounts = await prisma.order.groupBy({
    by: ["priceId"],
    where: { status: "paid" },
    _count: { _all: true },
  });
  const prices = await prisma.price.findMany({ where: { id: { in: paidCounts.map((p) => p.priceId) } }, select: { id: true, assessmentId: true } });
  const priceToAssessment = new Map(prices.map((p) => [p.id, p.assessmentId]));
  const paidByAssessmentId = new Map<string, number>();
  for (const p of paidCounts) {
    const assessmentId = priceToAssessment.get(p.priceId);
    if (!assessmentId) continue;
    paidByAssessmentId.set(assessmentId, (paidByAssessmentId.get(assessmentId) ?? 0) + p._count._all);
  }

  const assessmentsWithIds = await prisma.assessment.findMany({ select: { id: true, slug: true } });
  const slugToId = new Map(assessmentsWithIds.map((a) => [a.slug, a.id]));

  return assessments
    .map((a) => ({
      slug: a.slug,
      name: a.name,
      completions: a._count.assessmentSessions,
      paidOrders: paidByAssessmentId.get(slugToId.get(a.slug) ?? "") ?? 0,
    }))
    .sort((a, b) => b.completions - a.completions)
    .slice(0, limit);
}

export interface TopSourceRow {
  source: string;
  sessions: number;
  paidOrders: number;
}

/** First-touch attribution — AnonymousSession.utmSource is set once, on creation, and never overwritten (lib/anonymousSession.ts). */
export async function getTopAcquisitionSources(limit = 5): Promise<TopSourceRow[]> {
  const grouped = await prisma.anonymousSession.groupBy({
    by: ["utmSource"],
    _count: { _all: true },
  });

  const paidSessions = await prisma.order.findMany({
    where: { status: "paid" },
    select: { assessmentSession: { select: { anonymousSession: { select: { utmSource: true } } } } },
  });
  const paidBySource = new Map<string, number>();
  for (const o of paidSessions) {
    const source = o.assessmentSession.anonymousSession.utmSource ?? "(direct)";
    paidBySource.set(source, (paidBySource.get(source) ?? 0) + 1);
  }

  return grouped
    .map((g) => ({
      source: g.utmSource ?? "(direct)",
      sessions: g._count._all,
      paidOrders: paidBySource.get(g.utmSource ?? "(direct)") ?? 0,
    }))
    .sort((a, b) => b.sessions - a.sessions)
    .slice(0, limit);
}

export interface TopCampaignRow {
  source: string;
  campaign: string;
  sessions: number;
  paidOrders: number;
}

/** Same first-touch attribution as getTopAcquisitionSources, grouped one level deeper — source is often not enough to tell two creatives or audiences apart. */
export async function getTopCampaigns(limit = 8): Promise<TopCampaignRow[]> {
  const grouped = await prisma.anonymousSession.groupBy({
    by: ["utmSource", "utmCampaign"],
    where: { utmCampaign: { not: null } },
    _count: { _all: true },
  });

  const paidSessions = await prisma.order.findMany({
    where: { status: "paid" },
    select: { assessmentSession: { select: { anonymousSession: { select: { utmSource: true, utmCampaign: true } } } } },
  });
  const paidByKey = new Map<string, number>();
  for (const o of paidSessions) {
    const { utmSource, utmCampaign } = o.assessmentSession.anonymousSession;
    if (!utmCampaign) continue;
    const key = `${utmSource ?? "(direct)"}::${utmCampaign}`;
    paidByKey.set(key, (paidByKey.get(key) ?? 0) + 1);
  }

  return grouped
    .map((g) => ({
      source: g.utmSource ?? "(direct)",
      campaign: g.utmCampaign as string,
      sessions: g._count._all,
      paidOrders: paidByKey.get(`${g.utmSource ?? "(direct)"}::${g.utmCampaign}`) ?? 0,
    }))
    .sort((a, b) => b.sessions - a.sessions)
    .slice(0, limit);
}

export interface TopRecommendationRow {
  fromSlug: string;
  toSlug: string;
  weight: number;
  impressions: number;
}

/** "Impressions" here means recommendation_viewed events recorded on the *source* assessment's report page — the closest signal currently tracked to per-edge performance (no recommendation_clicked event exists yet, see docs gap). */
export async function getTopRecommendations(limit = 5): Promise<TopRecommendationRow[]> {
  const rules = await prisma.recommendationRule.findMany({
    include: { fromAssessment: true, toAssessment: true },
    orderBy: { weight: "desc" },
  });

  const impressions = await prisma.event.groupBy({
    by: ["assessmentId"],
    where: { eventName: "recommendation_viewed" },
    _count: { _all: true },
  });
  const impressionsByAssessmentId = new Map(impressions.map((i) => [i.assessmentId, i._count._all]));

  return rules
    .map((r) => ({
      fromSlug: r.fromAssessment.slug,
      toSlug: r.toAssessment.slug,
      weight: r.weight,
      impressions: impressionsByAssessmentId.get(r.fromAssessmentId) ?? 0,
    }))
    .sort((a, b) => b.impressions - a.impressions)
    .slice(0, limit);
}
