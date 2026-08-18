/**
 * Pure aggregation + narration core for the Master Profile — deliberately
 * DB-free (see conditionMatching.ts's comment on why) so it's unit
 * testable without a live Postgres connection. All Prisma access lives in
 * lib/masterProfile.ts, which fetches the readings this expects and hands
 * them off.
 */

const STRENGTH_THRESHOLD = 65;
const FRICTION_THRESHOLD = 35;
// Points apart (0-100 scale) before two assessments' readings of the same
// dimension count as "divergent" rather than noise around one true value.
const DIVERGENCE_THRESHOLD = 25;

export interface MasterProfileDimensionReading {
  slug: string;
  assessmentName: string;
  score: number;
  confidence: number;
}

export interface MasterProfileDimension {
  key: string;
  label: string;
  averageScore: number;
  readings: MasterProfileDimensionReading[];
  divergent: boolean;
}

export type MasterProfileInsightKind = "consistent_strength" | "consistent_friction" | "divergent_pattern";

export interface MasterProfileInsight {
  kind: MasterProfileInsightKind;
  dimensionKey: string;
  dimensionLabel: string;
  summary: string;
}

/**
 * Turns raw per-dimension readings (one entry per completed assessment
 * that touched that dimension) into the averaged, divergence-flagged shape
 * the rest of the Master Profile is built from. Callers should only pass
 * dimensions with 2+ readings — a dimension only one assessment touched
 * belongs to that assessment's own report, not the cross-assessment view.
 */
export function aggregateDimension(
  key: string,
  label: string,
  readings: MasterProfileDimensionReading[]
): MasterProfileDimension {
  const confidenceSum = readings.reduce((sum, r) => sum + r.confidence, 0);
  const averageScore =
    confidenceSum > 0
      ? readings.reduce((sum, r) => sum + r.score * r.confidence, 0) / confidenceSum
      : readings.reduce((sum, r) => sum + r.score, 0) / readings.length;
  const spread = Math.max(...readings.map((r) => r.score)) - Math.min(...readings.map((r) => r.score));
  return { key, label, averageScore, readings, divergent: spread >= DIVERGENCE_THRESHOLD };
}

export function buildInsights(dimensions: MasterProfileDimension[]): MasterProfileInsight[] {
  const insights: MasterProfileInsight[] = [];

  const mostDivergent = [...dimensions].filter((d) => d.divergent).sort((a, b) => b.averageScore - a.averageScore)[0];
  if (mostDivergent) {
    const scores = mostDivergent.readings.map((r) => r.score);
    insights.push({
      kind: "divergent_pattern",
      dimensionKey: mostDivergent.key,
      dimensionLabel: mostDivergent.label,
      summary: `Your ${mostDivergent.label.toLowerCase()} isn't fixed — it reads differently depending on which pattern is being explored, from ${Math.round(Math.min(...scores))} to ${Math.round(Math.max(...scores))} across ${mostDivergent.readings.length} assessments.`,
    });
  }

  const strength = dimensions.find((d) => !d.divergent && d.averageScore >= STRENGTH_THRESHOLD);
  if (strength) {
    insights.push({
      kind: "consistent_strength",
      dimensionKey: strength.key,
      dimensionLabel: strength.label,
      summary: `${strength.label} shows up as a consistent thread across everything you've explored so far — it's not tied to one specific relationship or context.`,
    });
  }

  const friction = [...dimensions].reverse().find((d) => !d.divergent && d.averageScore <= FRICTION_THRESHOLD);
  if (friction) {
    insights.push({
      kind: "consistent_friction",
      dimensionKey: friction.key,
      dimensionLabel: friction.label,
      summary: `${friction.label} stays low across the patterns you've explored — a steady undercurrent rather than something specific to one situation.`,
    });
  }

  return insights.slice(0, 3);
}
