import type {
  AssessmentConfig,
  DimensionKey,
  DimensionState,
  Question,
  RecordedAnswer,
  TensionResult,
} from "./types";

/**
 * Per-answer contribution weights are authored in the range [-3, +3]
 * (strongly against the dimension .. strongly for it, 0 = neutral). Scoring
 * normalizes the running average of contributions per dimension into 0-100,
 * centered at 50. This keeps content authoring simple (pick a weight in
 * -3..3 per option) while giving a stable, auditable normalized score —
 * see docs/ARCHITECTURE.md §6.
 */
const CONTRIBUTION_RANGE = 3;
const CONFIDENCE_SATURATION_COUNT = 3; // contributing answers after which the count factor maxes out

export interface Contribution {
  questionKey: string;
  weight: number; // -3..3, as authored
}

/**
 * Walks every answer once and buckets each individual dimension
 * contribution by dimension, with provenance (which question produced it).
 * Single source of truth for both scoring and explainability — see
 * explainDimension below, which reuses this instead of re-deriving it.
 */
function collectContributions(
  config: AssessmentConfig,
  allQuestions: Question[],
  answers: RecordedAnswer[]
): Record<DimensionKey, Contribution[]> {
  const byDimension: Record<DimensionKey, Contribution[]> = {};
  for (const d of config.dimensions) byDimension[d.key] = [];

  const questionByKey = new Map(allQuestions.map((q) => [q.key, q]));

  for (const answer of answers) {
    const question = questionByKey.get(answer.questionKey);
    if (!question) continue;

    if ((question.type === "single_select" || question.type === "multi_select") && answer.selectedOptionKeys) {
      for (const optionKey of answer.selectedOptionKeys) {
        const option = question.options?.find((o) => o.key === optionKey);
        if (!option) continue;
        for (const [dimKey, weight] of Object.entries(option.dimensionContributions)) {
          if (weight === undefined || !byDimension[dimKey]) continue;
          byDimension[dimKey].push({ questionKey: answer.questionKey, weight });
        }
      }
    }

    if (question.type === "scale" && typeof answer.scaleValue === "number" && question.scaleDimension && question.scaleMax) {
      const dimKey = question.scaleDimension;
      if (byDimension[dimKey]) {
        const midpointNormalized = (answer.scaleValue - 1) / (question.scaleMax - 1) - 0.5; // -0.5..0.5
        byDimension[dimKey].push({ questionKey: answer.questionKey, weight: midpointNormalized * 2 * CONTRIBUTION_RANGE });
      }
    }
    // open_text answers don't contribute here directly — their AI-derived
    // nudges are collected separately and blended in under a hard cap.
  }

  return byDimension;
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

/**
 * Confidence blends two independent factors:
 *  - volume: more contributing answers → more confidence, saturating at
 *    CONFIDENCE_SATURATION_COUNT (further answers on an already-established
 *    dimension stop adding much — the same reasoning the adaptive engine
 *    uses to stop re-measuring it, see adaptiveRules.ts).
 *  - consistency: what fraction of those contributions agree in direction
 *    with the majority. Answers that mostly pull the same way (agreement
 *    close to 1) earn full confidence; answers that are evenly split
 *    (agreement 0.5) genuinely mean *less* certain, single-number
 *    conclusion — that's a real conflicting-signal case, not just noise
 *    (it may separately surface as a tension, see detectTensions).
 * Neutral (weight === 0) contributions count toward volume but are excluded
 * from the agreement calculation — they don't pull either direction.
 */
function confidenceFactors(contributions: Contribution[]): { count: number; consistency: number } {
  const count = contributions.length;
  const positive = contributions.filter((c) => c.weight > 0).length;
  const negative = contributions.filter((c) => c.weight < 0).length;
  const signed = positive + negative;
  const consistency = signed === 0 ? 1 : Math.max(positive, negative) / signed;
  return { count, consistency };
}

function confidenceFor(contributions: Contribution[]): number {
  const { count, consistency } = confidenceFactors(contributions);
  return Math.min(1, count / CONFIDENCE_SATURATION_COUNT) * consistency;
}

export function recomputeDimensionScores(
  config: AssessmentConfig,
  allQuestions: Question[],
  answers: RecordedAnswer[]
): Record<DimensionKey, DimensionState> {
  const contributionsByDimension = collectContributions(config, allQuestions, answers);

  const nudgeSums: Record<DimensionKey, number> = {};
  const nudgeCounts: Record<DimensionKey, number> = {};
  for (const answer of answers) {
    if (!answer.aiDimensionNudges) continue;
    for (const [dimKey, nudge] of Object.entries(answer.aiDimensionNudges)) {
      if (nudge === undefined || !contributionsByDimension[dimKey]) continue;
      nudgeSums[dimKey] = (nudgeSums[dimKey] ?? 0) + Math.max(-1, Math.min(1, nudge));
      nudgeCounts[dimKey] = (nudgeCounts[dimKey] ?? 0) + 1;
    }
  }

  const aiInfluenceCap = config.scoringModel.aiInfluenceCap; // e.g. 0.15 = semantic signal may shift a score by at most 15 points

  const result: Record<DimensionKey, DimensionState> = {};
  for (const d of config.dimensions) {
    const contributions = contributionsByDimension[d.key];
    const sum = contributions.reduce((s, c) => s + c.weight, 0);
    const average = contributions.length > 0 ? sum / contributions.length : 0;
    const structuredNormalized = normalize(average);

    const nudgeAverage = nudgeCounts[d.key] ? nudgeSums[d.key] / nudgeCounts[d.key] : 0;
    const aiShift = nudgeAverage * aiInfluenceCap * 100; // nudgeAverage in -1..1, so max shift = aiInfluenceCap*100 points
    const blendedNormalized = Math.max(0, Math.min(100, structuredNormalized + aiShift));

    result[d.key] = {
      raw: sum,
      // AI nudges shade the score but never count toward confidence — confidence
      // reflects structured-answer volume + consistency only, per docs/ARCHITECTURE.md §6.
      normalized: blendedNormalized,
      confidence: confidenceFor(contributions),
    };
  }
  return result;
}

export function overallConfidence(scores: Record<DimensionKey, DimensionState>): number {
  const values = Object.values(scores);
  if (values.length === 0) return 0;
  return values.reduce((sum, s) => sum + s.confidence, 0) / values.length;
}

export interface DimensionExplanation {
  dimensionKey: DimensionKey;
  contributingAnswers: Contribution[];
  count: number;
  positiveCount: number;
  negativeCount: number;
  neutralCount: number;
  consistency: number;
  aiNudgeCount: number;
  confidence: number;
}

/**
 * Traces a dimension's score back to the exact answers that produced it —
 * the "answers → signals → dimensions" half of the explainability chain
 * required alongside profileMatcher's explainProfileMatch (the
 * "dimensions → conditions → profile" half). Never used in the scoring hot
 * path itself; this is a reporting/debugging query computed on demand.
 */
export function explainDimension(
  config: AssessmentConfig,
  allQuestions: Question[],
  answers: RecordedAnswer[],
  dimensionKey: DimensionKey
): DimensionExplanation {
  const contributions = collectContributions(config, allQuestions, answers)[dimensionKey] ?? [];
  const { consistency } = confidenceFactors(contributions);
  const aiNudgeCount = answers.filter((a) => a.aiDimensionNudges?.[dimensionKey] !== undefined).length;

  return {
    dimensionKey,
    contributingAnswers: contributions,
    count: contributions.length,
    positiveCount: contributions.filter((c) => c.weight > 0).length,
    negativeCount: contributions.filter((c) => c.weight < 0).length,
    neutralCount: contributions.filter((c) => c.weight === 0).length,
    consistency,
    aiNudgeCount,
    confidence: confidenceFor(contributions),
  };
}

/**
 * A tension isn't an error — it's two strong tendencies coexisting (high
 * independence AND high connection is a real, meaningful pattern). Checked
 * against the assessment's authored tensionPairs; an assessment with none
 * simply detects none. See docs/ARCHITECTURE.md §6.
 */
/** Whether `score` clears `threshold` in the given direction, and how far past it (0..1, 1 = maximally past). */
function clearsThreshold(score: number, threshold: number, direction: "gte" | "lte"): { clears: boolean; excess: number } {
  if (direction === "lte") {
    return { clears: score <= threshold, excess: threshold <= 0 ? 1 : (threshold - score) / threshold };
  }
  return { clears: score >= threshold, excess: threshold >= 100 ? 1 : (score - threshold) / (100 - threshold) };
}

export function detectTensions(
  config: AssessmentConfig,
  scores: Record<DimensionKey, DimensionState>
): TensionResult[] {
  const results: TensionResult[] = [];

  for (const pair of config.tensionPairs ?? []) {
    const a = scores[pair.dimensionA]?.normalized;
    const b = scores[pair.dimensionB]?.normalized;
    if (a === undefined || b === undefined) continue;

    const sideA = clearsThreshold(a, pair.thresholdA, pair.directionA ?? "gte");
    const sideB = clearsThreshold(b, pair.thresholdB, pair.directionB ?? "gte");
    if (!sideA.clears || !sideB.clears) continue;

    const strength = Math.max(0, Math.min(1, (sideA.excess + sideB.excess) / 2));
    results.push({ key: pair.key, label: pair.label, dimensions: [pair.dimensionA, pair.dimensionB], strength });
  }

  return results.sort((x, y) => y.strength - x.strength);
}
