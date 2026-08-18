import type { RecommendationCandidate } from "@inner/assessment-engine";

/**
 * Deliberately DB-free — pulled out of lib/recommendation.ts so this (and
 * anything built on it, like lib/exploreRanking.ts) can be unit tested
 * without a live Postgres connection. Importing @inner/db at module scope
 * anywhere in the chain instantiates PrismaClient, which throws immediately
 * outside a real app process (no DATABASE_URL in the plain vitest env).
 */
export function matchesCondition(condition: RecommendationCandidate["condition"], scores: Record<string, number>): boolean {
  return Object.entries(condition.dimensionRanges).every(([dimKey, range]) => {
    if (!range) return true;
    const score = scores[dimKey] ?? 50;
    return score >= range[0] && score <= range[1];
  });
}
