// Domain types for the Assessment Engine — see docs/ARCHITECTURE.md §3 and §5.
// This package is framework-free and knows nothing about Next.js, Prisma, or
// any AI provider. It is the deterministic core: given a config and a
// sequence of answers, it decides what happens next.

export type DimensionKey = string;

export interface DimensionRef {
  key: DimensionKey;
  weight: number;
}

export type QuestionType = "single_select" | "multi_select" | "scale" | "open_text";

export interface QuestionOption {
  key: string;
  label: string;
  /** Contribution to each dimension's raw score if this option is selected. */
  dimensionContributions: Partial<Record<DimensionKey, number>>;
}

export type QuestionDifficulty = "easy" | "moderate" | "deep";

export interface Question {
  key: string;
  type: QuestionType;
  prompt: string;
  /** Core questions are always asked, in order, before any adaptive branching. */
  isCore: boolean;
  options?: QuestionOption[]; // absent for open_text
  /** For scale questions: contribution per unit, applied against the 1..scaleMax answer. */
  scaleMax?: number;
  scaleDimension?: DimensionKey;
  /**
   * open_text only: adaptivePool question keys Question AI may choose a
   * follow-up from after this answer (Phase 2, §4/§5). AI selects among
   * these — it can never invent a question outside this list.
   */
  dynamicFollowupCandidates?: string[];
  /**
   * Marks a question as emotionally loaded enough that the UI offers
   * "Prefer not to answer" instead of forcing a response. A skipped
   * question still consumes its askedQuestionKeys slot (never re-asked)
   * but contributes nothing to scoring.
   */
  sensitive?: boolean;
  /** Authoring-time signal only — not read by the selection algorithm itself. */
  difficulty?: QuestionDifficulty;
}

export type AdaptiveConditionOp = "gte" | "lte" | "between" | "answered_option" | "has_ai_choice";

export interface AdaptiveTrigger {
  /** Which just-answered question this rule considers. */
  questionKey: string;
  dimensionKey?: DimensionKey;
  op: AdaptiveConditionOp;
  value?: number | [number, number];
  optionKey?: string; // for answered_option
}

export type AdaptiveActionType = "ask_followup" | "increase_confidence" | "skip" | "ask_ai_chosen_followup";

export interface AdaptiveAction {
  type: AdaptiveActionType;
  /** Which question (from adaptivePool) to ask when type === 'ask_followup'. */
  followupQuestionKey?: string;
  /** Dimension whose confidence should be bumped when type === 'increase_confidence'. */
  dimensionKey?: DimensionKey;
  confidenceBoost?: number;
}

export interface AdaptiveRule {
  key: string;
  trigger: AdaptiveTrigger;
  action: AdaptiveAction;
  priority: number;
}

/**
 * Authored pairing between a dimension and a CONTEXTUAL clarifying question
 * to ask when that dimension's answers stop agreeing with each other
 * (detectContradictions in scoring.ts). This is deliberately distinct from
 * `AdaptiveRule` — it never accuses ("you said X but also Y"), it just asks
 * a neutral follow-up ("Which situation feels more like you?") whose
 * *phrasing* is entirely the content author's responsibility. Fires at most
 * once per dimension per session.
 */
export interface ContradictionFollowupRule {
  dimensionKey: DimensionKey;
  /** Must be a key in questionBank.adaptivePool. */
  questionKey: string;
}

export interface ProfileMatchingRule {
  /**
   * Required — all ranges must hold (inclusive) on normalized 0-100 scores
   * for this profile to even be a candidate. Kept as the base/required shape
   * so every existing assessment's simple matchingRule keeps working
   * unchanged; optionalConditions/excludeConditions are additive.
   */
  dimensionRanges: Partial<Record<DimensionKey, [number, number]>>;
  /** Not gating — each satisfied condition strengthens this profile's rank among other required-matching profiles (distinguishes similar profiles). */
  optionalConditions?: Partial<Record<DimensionKey, [number, number]>>;
  /** Disqualifying — if ANY of these ranges hold, this profile is excluded even if dimensionRanges matched. */
  excludeConditions?: Partial<Record<DimensionKey, [number, number]>>;
}

export interface ProfileDefinition {
  key: string;
  name: string;
  descriptionTemplate: string;
  matchingRule: ProfileMatchingRule;
  /** Tie-break order when multiple profiles satisfy required conditions with an equal optional-condition count. Higher wins. Defaults to 0. */
  priority?: number;
}

export interface FreeResultTemplate {
  headline: string; // e.g. "Your primary pattern is:"
  insightIntro: string;
  lockedInsightsLabel: string; // e.g. "Your answers revealed 3 additional patterns"
}

export interface ShareTemplate {
  /** e.g. "I discovered my INNER Love Profile:" */
  shareTitleTemplate: string;
  /** May reference {{profileName}} — replaced with the resolved primary profile name. Never includes raw answers or dimension scores. */
  shareTextTemplate: string;
}

/**
 * A named tension between two dimensions that can both run strong at once —
 * "high independence AND high connection" is a real, meaningful pattern, not
 * a data error. See docs/ARCHITECTURE.md §6 and scoring.ts's detectTensions.
 *
 * Each side is checked against its own threshold in its own direction
 * (default "gte", i.e. "at least this high") — most tensions are "both
 * sides run strong" (high independence AND high connection), but some are
 * naturally "high on one side, low on the other" (high independence AND
 * *low* tolerance for distance is just as real a coexisting pattern), so
 * either side can opt into "lte" instead.
 */
export interface TensionPairDefinition {
  key: string;
  label: string;
  dimensionA: DimensionKey;
  dimensionB: DimensionKey;
  thresholdA: number;
  thresholdB: number;
  directionA?: "gte" | "lte";
  directionB?: "gte" | "lte";
}

export interface TensionResult {
  key: string;
  label: string;
  dimensions: [DimensionKey, DimensionKey];
  /** 0..1 — how strongly both sides clear their threshold, not just whether they do. */
  strength: number;
}

export interface ContradictionResult {
  dimensionKey: DimensionKey;
  /** 0..1 — fraction of this dimension's signed contributions that agreed in direction. Always <1 here, since that's what makes it a contradiction. */
  consistency: number;
  positiveCount: number;
  negativeCount: number;
}

export interface ReportSection {
  key: string;
  title: string;
  promptRef: string;
}

export interface RecommendationCandidate {
  assessmentSlug: string;
  condition: ProfileMatchingRule;
  weight: number;
  bridgeCopy: string;
}

export interface PriceRef {
  productType: "individual" | "deep" | "bundle" | "couple" | "master";
  amountCents: number;
  currency: string;
}

export interface AssessmentConfig {
  slug: string;
  name: string;
  category: string;
  description: string;
  hook: string;
  targetAudience: string;
  dimensions: DimensionRef[];
  questionBank: {
    core: Question[];
    adaptivePool: Question[];
  };
  adaptiveRules: AdaptiveRule[];
  scoringModel: {
    normalization: "min-max";
    aiInfluenceCap: number;
  };
  profiles: ProfileDefinition[];
  freeResultTemplate: FreeResultTemplate;
  shareTemplate?: ShareTemplate;
  /** Configurable pairs the tension engine checks after every answer — optional so existing assessments without an authored set simply detect none. */
  tensionPairs?: TensionPairDefinition[];
  /** Optional contextual follow-up questions for contradiction-prone dimensions — see ContradictionFollowupRule. */
  contradictionFollowups?: ContradictionFollowupRule[];
  premiumReportStructure: ReportSection[];
  recommendedNext: RecommendationCandidate[];
  pricing: Record<string, PriceRef>;
  status: "draft" | "published" | "archived";
  version: number;
  minQuestions: number;
  recommendedQuestions: number;
  maxQuestions: number;
}

// --- Runtime session state -------------------------------------------------

export interface RecordedAnswer {
  questionKey: string;
  selectedOptionKeys?: string[];
  scaleValue?: number;
  openText?: string;
  answeredAt: string;
  /**
   * Baked in by the caller (apps/web) *before* this answer is recorded —
   * the engine treats it as data, not as something it calls AI to produce.
   * That's what keeps replay/reconstruction deterministic (docs/ARCHITECTURE.md §4).
   */
  aiDimensionNudges?: Partial<Record<DimensionKey, number>>; // each -1..1
  aiChosenFollowupKey?: string;
  /** True when the respondent chose "Prefer not to answer" on a sensitive question — recorded so it's never re-asked, but contributes nothing to scoring. */
  skipped?: boolean;
}

export interface DimensionState {
  raw: number;
  normalized: number;
  confidence: number; // 0..1
  /** 0..1 — what fraction of this dimension's contributing answers agreed in direction. 1 with no contributions (nothing to disagree). */
  consistency: number;
}

export interface SessionState {
  assessmentSlug: string;
  askedQuestionKeys: string[];
  answers: RecordedAnswer[];
  dimensionScores: Record<DimensionKey, DimensionState>;
  status: "in_progress" | "completed";
}

export interface ProfileResult {
  primary: ProfileDefinition;
  secondary: ProfileDefinition[];
}
