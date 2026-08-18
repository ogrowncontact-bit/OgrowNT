import type { RecommendationCandidate } from "@inner/assessment-engine";
import { matchesCondition } from "./conditionMatching";

/**
 * Pure ranking core for the explore catalog — deliberately DB-free (see
 * conditionMatching.ts's comment) so the exact logic that decides which
 * recommendation edges fire is unit-testable in isolation. All Postgres
 * access lives in lib/explorePersonalization.ts, which fetches the inputs
 * this expects and hands them off.
 */

export interface CompletedAssessmentInput {
  slug: string;
  /** This assessment's own dimension readings — never another assessment's. */
  scores: Record<string, number>;
  recommendedNext: RecommendationCandidate[];
}

export interface PersonalizedExploreItem {
  slug: string;
  completed: boolean;
  relevanceScore: number;
}

/**
 * Aggregates weighted edges from *every* completed assessment's
 * recommendedNext graph, not just one — a visitor who's completed three
 * assessments gets an order informed by all three, and a candidate that
 * multiple completed assessments independently point to outranks one that
 * only a single graph happens to favor. That's the "diversity" fix over
 * lib/recommendation.ts's selectRecommendation, which is deliberately
 * single-graph, single-pick (right for "what's next after the report you
 * just got"; wrong for "what should this whole catalog page lead with").
 *
 * Each completed assessment's conditions are evaluated against *its own*
 * `scores` only — never a scores object merged across assessments. Two
 * assessments can score the same shared dimension key very differently
 * (e.g. "security" from a jealousy session vs. a love session), and an
 * edge authored against one assessment's reading must not fire — or fail
 * to fire — because a different assessment's reading of the same key
 * happened to overwrite it in a shared object.
 */
export function rankBySlugWeights(params: {
  publishedSlugs: string[];
  completed: CompletedAssessmentInput[];
}): PersonalizedExploreItem[] {
  const completedSlugs = new Set(params.completed.map((c) => c.slug));

  if (params.completed.length === 0) {
    return params.publishedSlugs.map((slug) => ({ slug, completed: false, relevanceScore: 0 }));
  }

  const weightBySlug = new Map<string, number>();
  for (const c of params.completed) {
    for (const candidate of c.recommendedNext) {
      if (!params.publishedSlugs.includes(candidate.assessmentSlug)) continue;
      if (completedSlugs.has(candidate.assessmentSlug)) continue;
      if (!matchesCondition(candidate.condition, c.scores)) continue;
      weightBySlug.set(candidate.assessmentSlug, (weightBySlug.get(candidate.assessmentSlug) ?? 0) + candidate.weight);
    }
  }

  return params.publishedSlugs
    .map((slug) => ({ slug, completed: completedSlugs.has(slug), relevanceScore: weightBySlug.get(slug) ?? 0 }))
    .sort((a, b) => {
      if (a.completed !== b.completed) return a.completed ? 1 : -1;
      return b.relevanceScore - a.relevanceScore;
    });
}
