import { prisma } from "@inner/db";

/**
 * Read-only rollups for the admin analytics dashboard. Never surfaces answer
 * content (see docs/ARCHITECTURE.md §12) — the one place that queries
 * runtime.Response (getQuestionDropoff, below) counts rows grouped by
 * questionId only, never selecting selectedOptionIds/scaleValue, and
 * runtime.OpenResponse is never touched at all.
 */

export const FUNNEL_STAGES = [
  { key: "landing_view", label: "Landing view" },
  { key: "assessment_started", label: "Started" },
  { key: "assessment_completed", label: "Completed" },
  { key: "free_result_viewed", label: "Free result viewed" },
  { key: "paywall_viewed", label: "Paywall viewed" },
  { key: "checkout_started", label: "Checkout started" },
  { key: "payment_completed", label: "Purchased" },
] as const;

export interface FunnelRow {
  assessmentId: string;
  slug: string;
  name: string;
  counts: Partial<Record<(typeof FUNNEL_STAGES)[number]["key"], number>>;
}

export async function getFunnelSummary(): Promise<FunnelRow[]> {
  const [assessments, grouped] = await Promise.all([
    prisma.assessment.findMany({ orderBy: { name: "asc" } }),
    prisma.event.groupBy({
      by: ["assessmentId", "eventName"],
      _count: { _all: true },
      where: { assessmentId: { not: null } },
    }),
  ]);

  const countsByAssessment = new Map<string, FunnelRow["counts"]>();
  for (const g of grouped) {
    if (!g.assessmentId) continue;
    const bucket = countsByAssessment.get(g.assessmentId) ?? {};
    bucket[g.eventName as (typeof FUNNEL_STAGES)[number]["key"]] = g._count._all;
    countsByAssessment.set(g.assessmentId, bucket);
  }

  return assessments.map((a) => ({
    assessmentId: a.id,
    slug: a.slug,
    name: a.name,
    counts: countsByAssessment.get(a.id) ?? {},
  }));
}

export interface OrderRow {
  id: string;
  email: string;
  assessmentName: string;
  productType: string;
  amountCents: number;
  currency: string;
  status: string;
  createdAt: Date;
}

export async function getRecentOrders(limit = 50): Promise<OrderRow[]> {
  const orders = await prisma.order.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: { user: true, price: { include: { assessment: true } } },
  });
  return orders.map((o) => ({
    id: o.id,
    email: o.user.email,
    assessmentName: o.price.assessment.name,
    productType: o.price.productType,
    amountCents: o.amountCents,
    currency: o.currency,
    status: o.status,
    createdAt: o.createdAt,
  }));
}

export interface RevenueSummary {
  totalPaidCents: number;
  paidCount: number;
  refundedCents: number;
  refundedCount: number;
}

export async function getRevenueSummary(): Promise<RevenueSummary> {
  const [paidAgg, refundAgg] = await Promise.all([
    prisma.order.aggregate({ where: { status: "paid" }, _sum: { amountCents: true }, _count: { _all: true } }),
    prisma.refund.aggregate({ _sum: { amountCents: true }, _count: { _all: true } }),
  ]);
  return {
    totalPaidCents: paidAgg._sum.amountCents ?? 0,
    paidCount: paidAgg._count._all,
    refundedCents: refundAgg._sum.amountCents ?? 0,
    refundedCount: refundAgg._count._all,
  };
}

export interface QuestionDropoffRow {
  key: string;
  prompt: string;
  answered: number;
  pctOfStarted: number;
}

export interface QuestionDropoffResult {
  assessmentId: string;
  totalStarted: number;
  questions: QuestionDropoffRow[];
}

/**
 * Where in the core question sequence people stop, for one assessment's
 * published version. Only counts rows in runtime.Response grouped by
 * questionId — never reads selectedOptionIds/scaleValue, so no answer
 * content leaves runtime.* here.
 */
export async function getQuestionDropoff(assessmentId: string): Promise<QuestionDropoffResult | null> {
  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
    include: { questions: { where: { isCore: true }, orderBy: { orderHint: "asc" } } },
  });
  if (!version) return null;

  const [totalStarted, responseCounts] = await Promise.all([
    prisma.assessmentSession.count({ where: { assessmentId } }),
    prisma.response.groupBy({
      by: ["questionId"],
      _count: { _all: true },
      where: { assessmentSession: { assessmentId } },
    }),
  ]);

  const countByKey = new Map(responseCounts.map((r) => [r.questionId, r._count._all]));

  return {
    assessmentId,
    totalStarted,
    questions: version.questions.map((q) => {
      const answered = countByKey.get(q.key) ?? 0;
      return {
        key: q.key,
        prompt: q.prompt,
        answered,
        pctOfStarted: totalStarted > 0 ? Math.round((answered / totalStarted) * 100) : 0,
      };
    }),
  };
}

export interface OrderExportRow {
  id: string;
  createdAt: Date;
  email: string;
  assessmentName: string;
  productType: string;
  amountCents: number;
  currency: string;
  status: string;
}

export async function getAllOrdersForExport(): Promise<OrderExportRow[]> {
  const orders = await prisma.order.findMany({
    orderBy: { createdAt: "desc" },
    include: { user: true, price: { include: { assessment: true } } },
  });
  return orders.map((o) => ({
    id: o.id,
    createdAt: o.createdAt,
    email: o.user.email,
    assessmentName: o.price.assessment.name,
    productType: o.price.productType,
    amountCents: o.amountCents,
    currency: o.currency,
    status: o.status,
  }));
}

export interface DeletionRequestRow {
  id: string;
  status: string;
  requestedAt: Date;
  completedAt: Date | null;
}

/** Compliance audit trail for GDPR Art. 17 erasure requests (see lib/privacy.ts). Never exposes the (now-anonymized) email. */
export async function getDeletionRequests(limit = 20): Promise<DeletionRequestRow[]> {
  const rows = await prisma.deletionRequest.findMany({
    orderBy: { requestedAt: "desc" },
    take: limit,
  });
  return rows.map((r) => ({ id: r.id, status: r.status, requestedAt: r.requestedAt, completedAt: r.completedAt }));
}

export interface ConsentSummary {
  totalConsented: number;
  totalDeclined: number;
  totalUnsubscribed: number;
}

export async function getConsentSummary(): Promise<ConsentSummary> {
  const [consented, declined, unsubscribed] = await Promise.all([
    prisma.marketingConsent.count({ where: { consent: true } }),
    prisma.marketingConsent.count({ where: { consent: false } }),
    prisma.unsubscribe.count(),
  ]);
  return { totalConsented: consented, totalDeclined: declined, totalUnsubscribed: unsubscribed };
}

export interface AiModuleStats {
  module: string;
  totalCalls: number;
  okCalls: number;
  avgLatencyMs: number;
  totalInputTokens: number;
  totalOutputTokens: number;
}

/** Cost/latency monitoring (§7) — aggregated from AiCallLog, written via packages/ai's onAiCall() hook. */
export async function getAiCallStats(): Promise<AiModuleStats[]> {
  const [totals, okCounts] = await Promise.all([
    prisma.aiCallLog.groupBy({
      by: ["module"],
      _count: { _all: true },
      _avg: { latencyMs: true },
      _sum: { inputTokens: true, outputTokens: true },
    }),
    prisma.aiCallLog.groupBy({ by: ["module"], where: { ok: true }, _count: { _all: true } }),
  ]);
  const okByModule = new Map(okCounts.map((r) => [r.module, r._count._all]));

  return totals
    .map((g) => ({
      module: g.module,
      totalCalls: g._count._all,
      okCalls: okByModule.get(g.module) ?? 0,
      avgLatencyMs: Math.round(g._avg.latencyMs ?? 0),
      totalInputTokens: g._sum.inputTokens ?? 0,
      totalOutputTokens: g._sum.outputTokens ?? 0,
    }))
    .sort((a, b) => a.module.localeCompare(b.module));
}

export interface AiCallFailureRow {
  id: string;
  module: string;
  occurredAt: Date;
  errorReason: string | null;
}

export async function getRecentAiFailures(limit = 10): Promise<AiCallFailureRow[]> {
  const rows = await prisma.aiCallLog.findMany({
    where: { ok: false },
    orderBy: { occurredAt: "desc" },
    take: limit,
  });
  return rows.map((r) => ({ id: r.id, module: r.module, occurredAt: r.occurredAt, errorReason: r.errorReason }));
}
