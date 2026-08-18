import { prisma } from "@inner/db";
import { getAssessmentConfig } from "./assessments";
import { rankBySlugWeights, type CompletedAssessmentInput, type PersonalizedExploreItem } from "./exploreRanking";

export type { PersonalizedExploreItem } from "./exploreRanking";

/**
 * Fetches this visitor's completed-assessment history and hands it to the
 * pure ranking core in lib/exploreRanking.ts. A brand-new visitor (nothing
 * completed yet) gets every published slug back in its input order with
 * relevanceScore 0 — there's nothing to personalize on, so the page falls
 * back to today's plain catalog list.
 */
export async function rankExploreCandidates(params: {
  anonymousSessionId: string;
  publishedSlugs: string[];
}): Promise<PersonalizedExploreItem[]> {
  const completedSessions = await prisma.assessmentSession.findMany({
    where: { anonymousSessionId: params.anonymousSessionId, status: "completed" },
    include: { assessment: true, dimensionScores: true },
  });

  if (completedSessions.length === 0) {
    return rankBySlugWeights({ publishedSlugs: params.publishedSlugs, completed: [] });
  }

  const uniqueSlugs = [...new Set(completedSessions.map((s) => s.assessment.slug))];
  const configsBySlug = new Map(
    await Promise.all(uniqueSlugs.map(async (slug) => [slug, await getAssessmentConfig(slug)] as const))
  );

  const completed: CompletedAssessmentInput[] = completedSessions
    .map((session): CompletedAssessmentInput | null => {
      const config = configsBySlug.get(session.assessment.slug);
      if (!config) return null;
      return {
        slug: session.assessment.slug,
        scores: Object.fromEntries(session.dimensionScores.map((d) => [d.dimensionKey, d.normalizedScore])),
        recommendedNext: config.recommendedNext,
      };
    })
    .filter((c): c is CompletedAssessmentInput => c !== null);

  return rankBySlugWeights({ publishedSlugs: params.publishedSlugs, completed });
}
