import { prisma, type FeedbackRating } from "@inner/db";

export interface FeedbackRow {
  id: string;
  rating: FeedbackRating;
  comment: string | null;
  createdAt: Date;
  language: string;
  assessmentSlug: string;
  assessmentName: string;
}

export interface FeedbackFilters {
  assessmentSlug?: string;
  rating?: FeedbackRating;
  language?: string;
  from?: Date;
  to?: Date;
}

const RATING_LABELS: Record<FeedbackRating, string> = {
  very_accurate: "Very accurate",
  mostly_accurate: "Mostly accurate",
  somewhat_accurate: "Somewhat accurate",
  not_very_accurate: "Not very accurate",
  not_accurate: "Not accurate",
};

export { RATING_LABELS };

/** FASE 32 §ADMIN FEEDBACK — filterable by product/rating/language/date, never surfaces anything beyond what the visitor themselves submitted. */
export async function listFeedback(filters: FeedbackFilters = {}, limit = 200): Promise<FeedbackRow[]> {
  const rows = await prisma.reportFeedback.findMany({
    where: {
      rating: filters.rating,
      createdAt: filters.from || filters.to ? { gte: filters.from, lte: filters.to } : undefined,
      report: {
        language: filters.language,
        assessmentSession: filters.assessmentSlug ? { sourceSlug: filters.assessmentSlug } : undefined,
      },
    },
    orderBy: { createdAt: "desc" },
    take: limit,
    include: { report: { include: { assessmentSession: { include: { assessment: true } } } } },
  });

  return rows.map((r) => ({
    id: r.id,
    rating: r.rating,
    comment: r.comment,
    createdAt: r.createdAt,
    language: r.report.language,
    assessmentSlug: r.report.assessmentSession.sourceSlug,
    assessmentName: r.report.assessmentSession.assessment.name,
  }));
}

export async function getFeedbackSummary(): Promise<{ total: number; byRating: { rating: FeedbackRating; count: number }[] }> {
  const [total, grouped] = await Promise.all([
    prisma.reportFeedback.count(),
    prisma.reportFeedback.groupBy({ by: ["rating"], _count: { _all: true } }),
  ]);
  return {
    total,
    byRating: grouped.map((g) => ({ rating: g.rating, count: g._count._all })),
  };
}
