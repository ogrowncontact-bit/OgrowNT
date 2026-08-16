import { prisma } from "@inner/db";
import type { AssessmentConfig, Question, QuestionOption } from "@inner/assessment-engine";

/**
 * Reconstructs an AssessmentConfig from the catalog.* tables — this is the
 * live source of truth as of Phase 5. The static configs in @inner/content
 * are seed data only now (see prisma/seed.ts); nothing here reads them.
 * This is what actually makes the admin builder meaningful: a change saved
 * there is live the next time this function runs, no deploy involved.
 */

interface QuestionMetadata {
  scaleMax?: number;
  scaleDimension?: string;
  dynamicFollowupCandidates?: string[];
}

function toQuestion(row: {
  key: string;
  type: string;
  isCore: boolean;
  prompt: string;
  metadata: unknown;
  options: { key: string; label: string; dimensionContributions: unknown; orderHint: number }[];
}): Question {
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
  };
}

export async function getAssessmentConfig(slug: string): Promise<AssessmentConfig | null> {
  const assessment = await prisma.assessment.findUnique({ where: { slug } });
  if (!assessment || assessment.status !== "published") return null;

  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId: assessment.id, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
    include: {
      dimensions: { include: { dimension: true } },
      questions: { include: { options: true }, orderBy: { orderHint: "asc" } },
      adaptiveRules: true,
      profiles: true,
      reportTemplate: true,
    },
  });
  if (!version) return null;

  const recommendations = await prisma.recommendationRule.findMany({
    where: { fromAssessmentId: assessment.id },
    include: { toAssessment: true },
  });

  const prices = await prisma.price.findMany({ where: { assessmentId: assessment.id, active: true } });

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
    })),
    freeResultTemplate,
    premiumReportStructure: (version.reportTemplate?.sections as unknown as AssessmentConfig["premiumReportStructure"]) ?? [],
    recommendedNext: recommendations.map((r) => ({
      assessmentSlug: r.toAssessment.slug,
      condition: r.condition as unknown as AssessmentConfig["recommendedNext"][number]["condition"],
      weight: r.weight,
      bridgeCopy: r.bridgeCopy,
    })),
    pricing: Object.fromEntries(
      prices.map((p) => [p.productType, { productType: p.productType, amountCents: p.amountCents, currency: p.currency }])
    ),
  };
}

export async function listPublishedSlugs(): Promise<string[]> {
  const rows = await prisma.assessment.findMany({ where: { status: "published" }, select: { slug: true } });
  return rows.map((r) => r.slug);
}
