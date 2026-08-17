import { rankProfiles } from "./profileMatcher";
import { detectTensions } from "./scoring";
import type { AdaptiveRule, AssessmentConfig, DimensionKey, DimensionState, Question, RecordedAnswer } from "./types";

function ruleMatches(
  rule: AdaptiveRule,
  lastAnswer: RecordedAnswer,
  dimensionScores: Record<DimensionKey, DimensionState>
): boolean {
  if (rule.trigger.questionKey !== lastAnswer.questionKey) return false;

  const { op, value, optionKey, dimensionKey } = rule.trigger;

  if (op === "answered_option") {
    return !!optionKey && !!lastAnswer.selectedOptionKeys?.includes(optionKey);
  }

  if (op === "has_ai_choice") {
    return !!lastAnswer.aiChosenFollowupKey;
  }

  if (!dimensionKey) return false;
  const score = dimensionScores[dimensionKey]?.normalized;
  if (score === undefined) return false;

  if (op === "gte" && typeof value === "number") return score >= value;
  if (op === "lte" && typeof value === "number") return score <= value;
  if (op === "between" && Array.isArray(value)) return score >= value[0] && score <= value[1];
  return false;
}

function questionDimensions(q: Question): DimensionKey[] {
  if (q.type === "scale") return q.scaleDimension ? [q.scaleDimension] : [];
  const dims = new Set<DimensionKey>();
  for (const opt of q.options ?? []) {
    for (const dimKey of Object.keys(opt.dimensionContributions)) dims.add(dimKey);
  }
  return [...dims];
}

const CLARIFY_UNCERTAINTY_WEIGHT = 2.0;
const EXPLORE_TENSION_WEIGHT = 1.5;
const DISTINGUISH_PROFILES_WEIGHT = 1.2;
const DEEPEN_STRONG_SIGNAL_WEIGHT = 0.5;
const AVOID_SATURATED_PENALTY = 1.5;
const SATURATED_CONFIDENCE = 0.85;
const HIGH_VALUE_THRESHOLD = 1.5;

/**
 * Ranks the still-unasked adaptive pool by expected information value, so
 * the engine can decide *which* extra question is worth asking instead of
 * mechanically working through a list. Four factors, each grounded in what
 * the assessment already knows about itself after every answer so far:
 *
 *  - clarify uncertain dimensions (low confidence — the dominant factor)
 *  - explore a detected tension (both sides of a real coexisting pattern)
 *  - distinguish the two currently-closest candidate profiles (a "swing"
 *    dimension that separates them)
 *  - deepen an already-directional-but-not-yet-saturated signal
 *
 * and one thing it actively avoids: re-measuring a dimension whose
 * confidence has already saturated. open_text questions are excluded from
 * this generic pick — they're only ever reached deliberately, via an
 * authored adaptiveRule or Question AI's dynamicFollowupCandidates, never a
 * drive-by information-value pick.
 */
export function selectByInformationValue(
  config: AssessmentConfig,
  askedQuestionKeys: string[],
  dimensionScores: Record<DimensionKey, DimensionState>
): string | null {
  const askedSet = new Set(askedQuestionKeys);
  const unaskedPool = config.questionBank.adaptivePool.filter((q) => !askedSet.has(q.key) && q.type !== "open_text");
  if (unaskedPool.length === 0) return null;

  const tensionDimensions = new Set(detectTensions(config, dimensionScores).flatMap((t) => t.dimensions));

  const top2 = rankProfiles(config, dimensionScores).slice(0, 2);
  const swingDimensions = new Set(top2.flatMap((r) => Object.keys(r.profile.matchingRule.dimensionRanges)));

  let best: { key: string; value: number } | null = null;
  for (const q of unaskedPool) {
    const dims = questionDimensions(q);
    if (dims.length === 0) continue;

    let value = 0;
    for (const dim of dims) {
      const state = dimensionScores[dim];
      const confidence = state?.confidence ?? 0;
      const strength = Math.abs((state?.normalized ?? 50) - 50) / 50;

      value += (1 - confidence) * CLARIFY_UNCERTAINTY_WEIGHT;
      if (tensionDimensions.has(dim)) value += EXPLORE_TENSION_WEIGHT;
      if (swingDimensions.has(dim)) value += DISTINGUISH_PROFILES_WEIGHT;
      if (confidence >= 0.3 && confidence < SATURATED_CONFIDENCE && strength > 0.4) value += DEEPEN_STRONG_SIGNAL_WEIGHT;
      if (confidence >= SATURATED_CONFIDENCE) value -= AVOID_SATURATED_PENALTY;
    }
    value /= dims.length;

    if (!best || value > best.value) best = { key: q.key, value };
  }

  return best?.key ?? null;
}

export interface NextStep {
  type: "ask_followup" | "ask_core" | "complete";
  questionKey?: string;
}

/**
 * Deterministic adaptive engine — decides *whether* and *which slot* to
 * branch into. AI (Question AI, Phase 2) only phrases/selects within the
 * `ask_followup` question it's handed here; it never decides on its own to
 * extend the interview. See docs/ARCHITECTURE.md §5.
 *
 * Three layers, in authority order: (1) explicit authored adaptiveRules —
 * specific, high-confidence branch logic the content author chose to name
 * outright; (2) the fixed core question bank — the baseline every session
 * gets; (3) once core is exhausted, information-value selection over the
 * remaining adaptive pool, which is what lets the interview length itself
 * vary by how much clarification a given person's answers actually need,
 * within [minQuestions, maxQuestions] and never forced to the max.
 */
export function decideNextStep(
  config: AssessmentConfig,
  askedQuestionKeys: string[],
  answers: RecordedAnswer[],
  dimensionScores: Record<DimensionKey, DimensionState>
): NextStep {
  const askedSet = new Set(askedQuestionKeys);
  const lastAnswer = answers[answers.length - 1];

  // Hard safeguard: never exceed maxQuestions regardless of pending rules.
  if (askedQuestionKeys.length >= config.maxQuestions) {
    return { type: "complete" };
  }

  // Layer 1: explicit adaptive rules triggered by the most recent answer, highest priority first.
  if (lastAnswer) {
    const candidates = config.adaptiveRules
      .filter((r) => ruleMatches(r, lastAnswer, dimensionScores))
      .sort((a, b) => b.priority - a.priority);

    for (const rule of candidates) {
      if (rule.action.type === "ask_followup" && rule.action.followupQuestionKey) {
        if (!askedSet.has(rule.action.followupQuestionKey)) {
          return { type: "ask_followup", questionKey: rule.action.followupQuestionKey };
        }
      }
      if (rule.action.type === "ask_ai_chosen_followup" && lastAnswer.aiChosenFollowupKey) {
        // The candidate itself was already validated (against the question's
        // dynamicFollowupCandidates) by the caller before this was recorded —
        // the engine just has to honor it, same de-dup rule as any other slot.
        if (!askedSet.has(lastAnswer.aiChosenFollowupKey)) {
          return { type: "ask_followup", questionKey: lastAnswer.aiChosenFollowupKey };
        }
      }
      // 'increase_confidence' and 'skip' actions affect scoring/flow bookkeeping
      // upstream (engine.ts) rather than producing a question here.
    }
  }

  // Layer 2: next unanswered core question, in order.
  const nextCore = config.questionBank.core.find((q) => !askedSet.has(q.key));
  if (nextCore) {
    if (askedQuestionKeys.length >= config.recommendedQuestions && askedQuestionKeys.length >= config.minQuestions) {
      // Past the recommended length with no pending high-signal rule — wrap up
      // rather than mechanically exhausting the rest of the core bank.
      return { type: "complete" };
    }
    return { type: "ask_core", questionKey: nextCore.key };
  }

  // Layer 3: core is exhausted — decide whether more clarification is worth it.
  const asked = askedQuestionKeys.length;

  if (asked < config.minQuestions) {
    // Haven't hit the floor yet — take the best available candidate regardless of its value.
    const candidate = selectByInformationValue(config, askedQuestionKeys, dimensionScores);
    return candidate ? { type: "ask_followup", questionKey: candidate } : { type: "complete" };
  }

  if (asked >= config.recommendedQuestions) {
    // Past the recommended length — only keep going for a genuinely high-value candidate.
    const candidate = selectByInformationValue(config, askedQuestionKeys, dimensionScores);
    if (!candidate) return { type: "complete" };
    const dims = questionDimensions(
      [...config.questionBank.core, ...config.questionBank.adaptivePool].find((q) => q.key === candidate)!
    );
    const tensionDimensions = new Set(detectTensions(config, dimensionScores).flatMap((t) => t.dimensions));
    const worthIt = dims.some((d) => (dimensionScores[d]?.confidence ?? 0) < 0.3 || tensionDimensions.has(d));
    return worthIt ? { type: "ask_followup", questionKey: candidate } : { type: "complete" };
  }

  // Between min and recommended — keep clarifying if there's anything worth asking.
  const candidate = selectByInformationValue(config, askedQuestionKeys, dimensionScores);
  return candidate ? { type: "ask_followup", questionKey: candidate } : { type: "complete" };
}
