import type { AdaptiveRule, AssessmentConfig, DimensionKey, DimensionState, RecordedAnswer } from "./types";

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

export interface NextStep {
  type: "ask_followup" | "ask_core" | "complete";
  questionKey?: string;
}

/**
 * Deterministic adaptive engine — decides *whether* and *which slot* to
 * branch into. AI (Question AI, Phase 2) only phrases/selects within the
 * `ask_followup` question it's handed here; it never decides on its own to
 * extend the interview. See docs/ARCHITECTURE.md §5.
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

  // Evaluate adaptive rules triggered by the most recent answer, highest priority first.
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

  // Next unanswered core question, in order.
  const nextCore = config.questionBank.core.find((q) => !askedSet.has(q.key));
  if (nextCore) {
    if (
      askedQuestionKeys.length >= config.recommendedQuestions &&
      askedQuestionKeys.length >= config.minQuestions
    ) {
      // Past the recommended length with no pending high-signal rule — wrap up
      // rather than mechanically exhausting the rest of the core bank.
      return { type: "complete" };
    }
    return { type: "ask_core", questionKey: nextCore.key };
  }

  return { type: "complete" };
}
