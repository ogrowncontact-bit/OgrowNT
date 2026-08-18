import { prisma } from "@inner/db";

export interface AdminRecommendationRow {
  fromAssessmentId: string;
  fromSlug: string;
  fromName: string;
  toSlug: string;
  toName: string;
  weight: number;
  bridgeCopy: string;
  conditionSummary: string;
}

function summarizeCondition(condition: unknown): string {
  const ranges = (condition as { dimensionRanges?: Record<string, [number, number] | undefined> } | null)?.dimensionRanges;
  if (!ranges) return "always";
  const parts = Object.entries(ranges)
    .filter(([, range]) => !!range)
    .map(([key, range]) => `${key} ${range![0]}–${range![1]}`);
  return parts.length > 0 ? parts.join(", ") : "always";
}

/** The whole discovery graph in one place — actual edits stay in each source assessment's editor (RecommendationsEditor) to avoid a second write path for the same data. */
export async function listRecommendationsForAdmin(): Promise<AdminRecommendationRow[]> {
  const rules = await prisma.recommendationRule.findMany({
    include: { fromAssessment: true, toAssessment: true },
    orderBy: [{ fromAssessment: { name: "asc" } }, { weight: "desc" }],
  });

  return rules.map((r) => ({
    fromAssessmentId: r.fromAssessmentId,
    fromSlug: r.fromAssessment.slug,
    fromName: r.fromAssessment.name,
    toSlug: r.toAssessment.slug,
    toName: r.toAssessment.name,
    weight: r.weight,
    bridgeCopy: r.bridgeCopy,
    conditionSummary: summarizeCondition(r.condition),
  }));
}
