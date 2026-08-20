import { decideNextStep } from "./adaptiveRules";
import { matchProfiles } from "./profileMatcher";
import { detectContradictions, detectTensions, emptyDimensionScores, overallConfidence, recomputeDimensionScores } from "./scoring";
import type { AssessmentConfig, Question, RecordedAnswer, SessionState } from "./types";

function allQuestions(config: AssessmentConfig): Question[] {
  return [...config.questionBank.core, ...config.questionBank.adaptivePool];
}

/**
 * `state.askedQuestionKeys` holds *answered* question keys, in order — this
 * is what lets `nextQuestion`/`submitAnswer` be reconstructed purely from
 * persisted answer rows (see apps/web/lib/session.ts), with no separate
 * "what am I currently showing" field to keep in sync.
 */
export function startSession(config: AssessmentConfig): SessionState {
  return {
    assessmentSlug: config.slug,
    askedQuestionKeys: [],
    answers: [],
    dimensionScores: emptyDimensionScores(config),
    status: "in_progress",
  };
}

export function nextQuestion(config: AssessmentConfig, state: SessionState): Question | null {
  if (state.status === "completed") return null;
  const step = decideNextStep(config, state.askedQuestionKeys, state.answers, state.dimensionScores);
  if (step.type === "complete") return null;
  return allQuestions(config).find((q) => q.key === step.questionKey) ?? null;
}

export interface AnswerInput {
  questionKey: string;
  selectedOptionKeys?: string[];
  scaleValue?: number;
  openText?: string;
  aiDimensionNudges?: RecordedAnswer["aiDimensionNudges"];
  aiChosenFollowupKey?: string;
}

export interface AnswerResult {
  state: SessionState;
  nextQuestion: Question | null;
  isComplete: boolean;
  progress: { asked: number; recommended: number; max: number };
}

/** Records an answer, re-scores, and decides the next question (or completion) in one deterministic step. */
export function submitAnswer(config: AssessmentConfig, state: SessionState, input: AnswerInput): AnswerResult {
  const answer: RecordedAnswer = { ...input, answeredAt: new Date().toISOString() };
  const answers = [...state.answers, answer];
  const dimensionScores = recomputeDimensionScores(config, allQuestions(config), answers);
  const askedQuestionKeys = [...state.askedQuestionKeys, input.questionKey];

  const step = decideNextStep(config, askedQuestionKeys, answers, dimensionScores);

  const nextState: SessionState = {
    ...state,
    answers,
    dimensionScores,
    askedQuestionKeys,
    status: step.type === "complete" ? "completed" : "in_progress",
  };

  return {
    state: nextState,
    nextQuestion: step.type === "complete" ? null : allQuestions(config).find((q) => q.key === step.questionKey) ?? null,
    isComplete: step.type === "complete",
    progress: {
      asked: askedQuestionKeys.length,
      recommended: config.recommendedQuestions,
      max: config.maxQuestions,
    },
  };
}

export function computeResult(config: AssessmentConfig, state: SessionState) {
  const profileResult = matchProfiles(config, state.dimensionScores);
  return {
    profileResult,
    confidence: overallConfidence(state.dimensionScores),
    dimensionScores: state.dimensionScores,
    tensions: detectTensions(config, state.dimensionScores),
    contradictions: detectContradictions(config, allQuestions(config), state.answers),
  };
}
