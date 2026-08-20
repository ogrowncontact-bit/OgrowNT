import type { AssessmentConfig, Question, QuestionOption } from "@inner/assessment-engine";

/**
 * Shared catalog.* -> AssessmentConfig reconstruction, used by both the
 * public-facing loader (lib/assessments.ts, published versions only) and
 * the admin loader (lib/admin/catalogReader.ts, any version including
 * drafts) — one mapping, two callers with different version-selection
 * rules.
 */

interface QuestionMetadata {
  scaleMax?: number;
  scaleDimension?: string;
  dynamicFollowupCandidates?: string[];
  sensitive?: boolean;
  difficulty?: Question["difficulty"];
}

interface QuestionRow {
  key: string;
  type: string;
  isCore: boolean;
  prompt: string;
  metadata: unknown;
  options: { key: string; label: string; dimensionContributions: unknown; orderHint: number }[];
}

function toQuestion(row: QuestionRow): Question {
  const meta = (row.metadata as QuestionMetadata | null) ?? {};
  const options: QuestionOption[] | undefined = row.options.length
    ? [...row.options]
        .sort((a, b) => a.orderHint - b.orderHint)
        .map((o) => ({
          key: o.key,
          label: o.label,
          dimensionContributions: (o.dimensionContributions as QuestionOption["dimensionContributions"]) ?? {},
        }))
    : undefined;

  return {
    key: row.key,
    type: row.type as Question["type"],
    prompt: row.prompt,
    isCore: row.isCore,
    options,
    scaleMax: meta.scaleMax,
    scaleDimension: meta.scaleDimension,
    dynamicFollowupCandidates: meta.dynamicFollowupCandidates,
    sensitive: meta.sensitive,
    difficulty: meta.difficulty,
  };
}

export interface AssessmentRow {
  slug: string;
  name: string;
  category: string;
  description: string;
  hook: string;
  targetAudience: string;
  status: "draft" | "published" | "archived";
}

export interface VersionRow {
  versionNumber: number;
  minQuestions: number;
  recommendedQuestions: number;
  maxQuestions: number;
  aiInfluenceCap: number;
  freeResultTemplate: unknown;
  shareTemplate: unknown;
  tensionPairs: unknown;
  contradictionFollowups: unknown;
  dimensions: { weight: number; dimension: { key: string } }[];
  questions: QuestionRow[];
  adaptiveRules: { key: string; trigger: unknown; action: unknown; priority: number }[];
  profiles: { key: string; name: string; descriptionTemplate: string; matchingRule: unknown; priority: number }[];
  reportTemplate: { sections: unknown } | null;
}

export interface RecommendationRow {
  condition: unknown;
  weight: number;
  bridgeCopy: string;
  toAssessment: { slug: string };
}

export interface PriceRow {
  productType: string;
  amountCents: number;
  currency: string;
}

export function mapVersionToConfig(
  assessment: AssessmentRow,
  version: VersionRow,
  recommendations: RecommendationRow[],
  prices: PriceRow[]
): AssessmentConfig {
  const coreQuestions = version.questions.filter((q) => q.isCore).map(toQuestion);
  const adaptiveQuestions = version.questions.filter((q) => !q.isCore).map(toQuestion);

  const freeResultTemplate = (version.freeResultTemplate as AssessmentConfig["freeResultTemplate"] | null) ?? {
    headline: "Your primary pattern is:",
    insightIntro: "Your responses suggest a specific pattern worth exploring further.",
    lockedInsightsLabel: "Your answers revealed additional patterns.",
  };

  return {
    slug: assessment.slug,
    name: assessment.name,
    category: assessment.category,
    description: assessment.description,
    hook: assessment.hook,
    targetAudience: assessment.targetAudience,
    status: assessment.status,
    version: version.versionNumber,
    minQuestions: version.minQuestions,
    recommendedQuestions: version.recommendedQuestions,
    maxQuestions: version.maxQuestions,
    dimensions: version.dimensions.map((d) => ({ key: d.dimension.key, weight: d.weight })),
    scoringModel: { normalization: "min-max", aiInfluenceCap: version.aiInfluenceCap },
    questionBank: { core: coreQuestions, adaptivePool: adaptiveQuestions },
    adaptiveRules: version.adaptiveRules.map((r) => ({
      key: r.key,
      trigger: r.trigger as unknown as AssessmentConfig["adaptiveRules"][number]["trigger"],
      action: r.action as unknown as AssessmentConfig["adaptiveRules"][number]["action"],
      priority: r.priority,
    })),
    profiles: version.profiles.map((p) => ({
      key: p.key,
      name: p.name,
      descriptionTemplate: p.descriptionTemplate,
      matchingRule: p.matchingRule as unknown as AssessmentConfig["profiles"][number]["matchingRule"],
      priority: p.priority,
    })),
    freeResultTemplate,
    shareTemplate: (version.shareTemplate as AssessmentConfig["shareTemplate"] | null) ?? undefined,
    tensionPairs: (version.tensionPairs as AssessmentConfig["tensionPairs"] | null) ?? undefined,
    contradictionFollowups: (version.contradictionFollowups as AssessmentConfig["contradictionFollowups"] | null) ?? undefined,
    premiumReportStructure: (version.reportTemplate?.sections as unknown as AssessmentConfig["premiumReportStructure"]) ?? [],
    recommendedNext: recommendations.map((r) => ({
      assessmentSlug: r.toAssessment.slug,
      condition: r.condition as unknown as AssessmentConfig["recommendedNext"][number]["condition"],
      weight: r.weight,
      bridgeCopy: r.bridgeCopy,
    })),
    pricing: Object.fromEntries(
      prices.map((p) => [
        p.productType,
        {
          productType: p.productType as AssessmentConfig["pricing"][string]["productType"],
          amountCents: p.amountCents,
          currency: p.currency,
        },
      ])
    ) as AssessmentConfig["pricing"],
  };
}

export const VERSION_INCLUDE = {
  dimensions: { include: { dimension: true } },
  questions: { include: { options: true }, orderBy: { orderHint: "asc" as const } },
  adaptiveRules: true,
  profiles: true,
  reportTemplate: true,
} as const;
