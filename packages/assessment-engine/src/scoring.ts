import type { AssessmentConfig, DimensionKey, DimensionState, Question, RecordedAnswer } from "./types";

/**
 * Per-answer contribution weights are authored in the range [-3, +3]
 * (strongly against the dimension .. strongly for it, 0 = neutral). Scoring
 * normalizes the running average of contributions per dimension into 0-100,
 * centered at 50. This keeps content authoring simple (pick a weight in
 * -3..3 per option) while giving a stable, auditable normalized score —
 * see docs/ARCHITECTURE.md §6.
 */
const CONTRIBUTION_RANGE = 3;
const CONFIDENCE_SATURATION_COUNT = 3; // contributing answers after which confidence maxes out

export interface DimensionAccumulator {
  sum: number;
  count: number;
}

export function emptyDimensionScores(config: AssessmentConfig): Record<DimensionKey, DimensionState> {
  const out: Record<DimensionKey, DimensionState> = {};
  for (const d of config.dimensions) {
    out[d.key] = { raw: 0, normalized: 50, confidence: 0 };
  }
  return out;
}

function normalize(averageContribution: number): number {
  const clamped = Math.max(-CONTRIBUTION_RANGE, Math.min(CONTRIBUTION_RANGE, averageContribution));
  return 50 + (clamped / CONTRIBUTION_RANGE) * 50;
}

function confidenceFor(count: number): number {
  return Math.min(1, count / CONFIDENCE_SATURATION_COUNT);
}

/** Applies a single answer's dimension contributions on top of existing accumulators (raw = running sum, we track count via confidence math using raw/normalized history is lossy, so callers pass full answer history instead — see recomputeDimensionScores). */
export function recomputeDimensionScores(
  config: AssessmentConfig,
  allQuestions: Question[],
  answers: RecordedAnswer[]
): Record<DimensionKey, DimensionState> {
  const accumulators: Record<DimensionKey, DimensionAccumulator> = {};
  for (const d of config.dimensions) accumulators[d.key] = { sum: 0, count: 0 };

  const questionByKey = new Map(allQuestions.map((q) => [q.key, q]));

  for (const answer of answers) {
    const question = questionByKey.get(answer.questionKey);
    if (!question) continue;

    if ((question.type === "single_select" || question.type === "multi_select") && answer.selectedOptionKeys) {
      for (const optionKey of answer.selectedOptionKeys) {
        const option = question.options?.find((o) => o.key === optionKey);
        if (!option) continue;
        for (const [dimKey, weight] of Object.entries(option.dimensionContributions)) {
          if (weight === undefined || !accumulators[dimKey]) continue;
          accumulators[dimKey].sum += weight;
          accumulators[dimKey].count += 1;
        }
      }
    }

    if (question.type === "scale" && typeof answer.scaleValue === "number" && question.scaleDimension && question.scaleMax) {
      const dimKey = question.scaleDimension;
      if (accumulators[dimKey]) {
        const midpointNormalized = (answer.scaleValue - 1) / (question.scaleMax - 1) - 0.5; // -0.5..0.5
        accumulators[dimKey].sum += midpointNormalized * 2 * CONTRIBUTION_RANGE;
        accumulators[dimKey].count += 1;
      }
    }
    // open_text answers don't contribute here directly — their AI-derived
    // nudges are collected below and blended in under a hard cap.
  }

  const nudgeSums: Record<DimensionKey, number> = {};
  const nudgeCounts: Record<DimensionKey, number> = {};
  for (const answer of answers) {
    if (!answer.aiDimensionNudges) continue;
    for (const [dimKey, nudge] of Object.entries(answer.aiDimensionNudges)) {
      if (nudge === undefined || !accumulators[dimKey]) continue;
      nudgeSums[dimKey] = (nudgeSums[dimKey] ?? 0) + Math.max(-1, Math.min(1, nudge));
      nudgeCounts[dimKey] = (nudgeCounts[dimKey] ?? 0) + 1;
    }
  }

  const aiInfluenceCap = config.scoringModel.aiInfluenceCap; // e.g. 0.15 = semantic signal may shift a score by at most 15 points

  const result: Record<DimensionKey, DimensionState> = {};
  for (const d of config.dimensions) {
    const acc = accumulators[d.key];
    const average = acc.count > 0 ? acc.sum / acc.count : 0;
    const structuredNormalized = normalize(average);

    const nudgeAverage = nudgeCounts[d.key] ? nudgeSums[d.key] / nudgeCounts[d.key] : 0;
    const aiShift = nudgeAverage * aiInfluenceCap * 100; // nudgeAverage in -1..1, so max shift = aiInfluenceCap*100 points
    const blendedNormalized = Math.max(0, Math.min(100, structuredNormalized + aiShift));

    result[d.key] = {
      raw: acc.sum,
      // AI nudges shade the score but never count toward confidence — confidence
      // reflects structured-answer volume only, per docs/ARCHITECTURE.md §6.
      normalized: blendedNormalized,
      confidence: confidenceFor(acc.count),
    };
  }
  return result;
}

export function overallConfidence(scores: Record<DimensionKey, DimensionState>): number {
  const values = Object.values(scores);
  if (values.length === 0) return 0;
  return values.reduce((sum, s) => sum + s.confidence, 0) / values.length;
}
