import { prisma } from "@inner/db";
import { generateRecommendationCopy } from "@inner/ai";
import { dimensionPool } from "@inner/content/dimensions";
import type { AssessmentConfig, RecommendationCandidate } from "@inner/assessment-engine";
import { getAssessmentConfig, listPublishedSlugs } from "./assessments";
import { ensureAiTelemetryRegistered } from "./aiTelemetry";

// See the comment in app/api/sessions/[id]/answer/route.ts — registered per
// module realm, not just once globally via instrumentation.ts.
ensureAiTelemetryRegistered();

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

export interface Recommendation {
  slug: string;
  name: string;
  hook: string;
  bridgeCopy: string;
}

function matchesCondition(condition: RecommendationCandidate["condition"], scores: Record<string, number>): boolean {
  return Object.entries(condition.dimensionRanges).every(([dimKey, range]) => {
    if (!range) return true;
    const score = scores[dimKey] ?? 50;
    return score >= range[0] && score <= range[1];
  });
}

/**
 * Deterministic candidate selection first (config-declared graph, filtered
 * to published + not-already-completed), AI only narrates the bridge for
 * whichever candidate that picks — it can't recommend something irrelevant
 * or unpublished. See docs/ARCHITECTURE.md §8.
 */
export async function selectRecommendation(params: {
  anonymousSessionId: string;
  fromConfig: AssessmentConfig;
  primaryProfileName: string;
  dimensionScores: Record<string, number>;
}): Promise<Recommendation | null> {
  const completedSessions = await prisma.assessmentSession.findMany({
    where: { anonymousSessionId: params.anonymousSessionId, status: "completed" },
    include: { assessment: true },
  });
  const completedSlugs = new Set(completedSessions.map((s) => s.assessment.slug));
  const publishedSlugs = await listPublishedSlugs();

  const eligible = params.fromConfig.recommendedNext.filter(
    (c) => publishedSlugs.includes(c.assessmentSlug) && !completedSlugs.has(c.assessmentSlug)
  );
  const matching = eligible
    .filter((c) => matchesCondition(c.condition, params.dimensionScores))
    .sort((a, b) => b.weight - a.weight);

  let chosenSlug: string | undefined = matching[0]?.assessmentSlug ?? eligible[0]?.assessmentSlug;
  let staticBridgeCopy: string | undefined = (matching[0] ?? eligible[0])?.bridgeCopy;

  if (!chosenSlug) {
    // Last resort: any other published, not-yet-completed experience, so a
    // recommendation still appears even outside the curated graph.
    chosenSlug = publishedSlugs.find((slug) => slug !== params.fromConfig.slug && !completedSlugs.has(slug));
  }
  if (!chosenSlug) return null;

  const targetConfig = await getAssessmentConfig(chosenSlug);
  if (!targetConfig) return null;

  const topDimension = Object.entries(params.dimensionScores).sort((a, b) => b[1] - a[1])[0];
  const topDimensionLabel = topDimension ? (dimensionLabels[topDimension[0]] ?? topDimension[0]) : "your top pattern";

  const generated = await generateRecommendationCopy({
    fromAssessmentName: params.fromConfig.name,
    primaryProfileName: params.primaryProfileName,
    topDimensionLabel,
    targetAssessmentName: targetConfig.name,
    targetAssessmentHook: targetConfig.hook,
  });

  const bridgeCopy = generated?.bridgeCopy ?? staticBridgeCopy ?? `Curious what "${targetConfig.name}" might reveal?`;

  return { slug: targetConfig.slug, name: targetConfig.name, hook: targetConfig.hook, bridgeCopy };
}
