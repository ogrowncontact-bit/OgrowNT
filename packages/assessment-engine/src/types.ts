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
}

export type AdaptiveConditionOp = "gte" | "lte" | "between" | "answered_option";

export interface AdaptiveTrigger {
  /** Which just-answered question this rule considers. */
  questionKey: string;
  dimensionKey?: DimensionKey;
  op: AdaptiveConditionOp;
  value?: number | [number, number];
  optionKey?: string; // for answered_option
}

export type AdaptiveActionType = "ask_followup" | "increase_confidence" | "skip";

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

export interface ProfileMatchingRule {
  /** All ranges must hold (inclusive) on normalized 0-100 scores for this profile to match. */
  dimensionRanges: Partial<Record<DimensionKey, [number, number]>>;
}

export interface ProfileDefinition {
  key: string;
  name: string;
  descriptionTemplate: string;
  matchingRule: ProfileMatchingRule;
}

export interface FreeResultTemplate {
  headline: string; // e.g. "Your primary pattern is:"
  insightIntro: string;
  lockedInsightsLabel: string; // e.g. "Your answers revealed 3 additional patterns"
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
}

export interface DimensionState {
  raw: number;
  normalized: number;
  confidence: number; // 0..1
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
