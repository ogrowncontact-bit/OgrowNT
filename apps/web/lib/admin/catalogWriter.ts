import { prisma } from "@inner/db";
import type { AssessmentConfig } from "@inner/assessment-engine";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export interface CreateAssessmentInput {
  slug: string;
  name: string;
  category: string;
  hook: string;
  description: string;
  targetAudience: string;
}

/** Creates the Assessment row (status: draft) plus an empty starter draft version, ready to fill in via the builder. */
export async function createAssessment(input: CreateAssessmentInput): Promise<{ id: string }> {
  const slug = input.slug.trim().toLowerCase();
  if (!SLUG_PATTERN.test(slug)) {
    throw new Error("Slug must be lowercase letters, numbers, and hyphens only (e.g. \"my-new-experience\")");
  }

  const existing = await prisma.assessment.findUnique({ where: { slug } });
  if (existing) throw new Error(`Slug "${slug}" is already in use`);

  const assessment = await prisma.assessment.create({
    data: {
      slug,
      name: input.name,
      category: input.category,
      description: input.description,
      hook: input.hook,
      targetAudience: input.targetAudience,
      status: "draft",
    },
  });

  await prisma.assessmentVersion.create({
    data: {
      assessmentId: assessment.id,
      versionNumber: 1,
      minQuestions: 6,
      recommendedQuestions: 9,
      maxQuestions: 12,
      aiInfluenceCap: 0.15,
      freeResultTemplate: {
        headline: "Your primary pattern is:",
        insightIntro: "Your responses suggest a specific pattern worth exploring further.",
        lockedInsightsLabel: "Your answers revealed additional patterns.",
      },
      publishedAt: null,
      reportTemplate: {
        create: {
          sections: [
            { key: "signature", title: "Your INNER Signature", promptRef: `${slug}.signature` },
            { key: "conclusion", title: "Your Personalized Conclusion", promptRef: `${slug}.conclusion` },
          ],
        },
      },
    },
  });

  // Seed real prices matching the builder's displayed defaults — without this,
  // an admin who never touches the Pricing section publishes a experience
  // nobody can actually buy (checkout has no active Price row to charge).
  await prisma.price.createMany({
    data: [
      { assessmentId: assessment.id, productType: "individual", amountCents: 799, currency: "EUR" },
      { assessmentId: assessment.id, productType: "deep", amountCents: 1299, currency: "EUR" },
    ],
  });

  return { id: assessment.id };
}

/** Deletes every nested row under a draft version, then the draft version row itself — used before either recreating or discarding it. */
async function deleteVersion(versionId: string): Promise<void> {
  await prisma.questionOption.deleteMany({ where: { question: { assessmentVersionId: versionId } } });
  await prisma.question.deleteMany({ where: { assessmentVersionId: versionId } });
  await prisma.adaptiveRule.deleteMany({ where: { assessmentVersionId: versionId } });
  await prisma.profile.deleteMany({ where: { assessmentVersionId: versionId } });
  await prisma.reportTemplate.deleteMany({ where: { assessmentVersionId: versionId } });
  await prisma.assessmentDimension.deleteMany({ where: { assessmentVersionId: versionId } });
  await prisma.assessmentVersion.delete({ where: { id: versionId } });
}

/**
 * Replaces the assessment's draft wholesale with the given config — no
 * diffing, matching the "edits happen on a draft, publishing snapshots it"
 * model (docs/ARCHITECTURE.md §10). Every dimension key referenced must
 * already exist in the global pool (catalog.Dimension); this only creates
 * the per-assessment weight rows, not new global dimensions.
 */
export async function saveAssessmentDraft(assessmentId: string, config: AssessmentConfig): Promise<{ versionId: string }> {
  const assessment = await prisma.assessment.findUniqueOrThrow({ where: { id: assessmentId } });

  await prisma.assessment.update({
    where: { id: assessmentId },
    data: {
      name: config.name,
      category: config.category,
      description: config.description,
      hook: config.hook,
      targetAudience: config.targetAudience,
    },
  });

  const existingDrafts = await prisma.assessmentVersion.findMany({ where: { assessmentId, publishedAt: null } });
  for (const d of existingDrafts) await deleteVersion(d.id);

  const maxVersion = await prisma.assessmentVersion.aggregate({ where: { assessmentId }, _max: { versionNumber: true } });
  const versionNumber = (maxVersion._max.versionNumber ?? 0) + 1;

  const dimensionRows = await Promise.all(
    config.dimensions.map(async (d) => {
      const dim = await prisma.dimension.findUnique({ where: { key: d.key } });
      if (!dim) throw new Error(`Unknown dimension "${d.key}"`);
      return { dimensionId: dim.id, weight: d.weight };
    })
  );

  const version = await prisma.assessmentVersion.create({
    data: {
      assessmentId,
      versionNumber,
      minQuestions: config.minQuestions,
      recommendedQuestions: config.recommendedQuestions,
      maxQuestions: config.maxQuestions,
      aiInfluenceCap: config.scoringModel.aiInfluenceCap,
      freeResultTemplate: config.freeResultTemplate as any,
      publishedAt: null,
      dimensions: { create: dimensionRows },
      questions: {
        create: [
          ...config.questionBank.core.map((q, i) => ({
            key: q.key,
            type: q.type,
            isCore: true,
            prompt: q.prompt,
            orderHint: i,
            metadata: { scaleMax: q.scaleMax, scaleDimension: q.scaleDimension, dynamicFollowupCandidates: q.dynamicFollowupCandidates },
            options: {
              create: (q.options ?? []).map((o, j) => ({
                key: o.key,
                label: o.label,
                dimensionContributions: o.dimensionContributions,
                orderHint: j,
              })),
            },
          })),
          ...config.questionBank.adaptivePool.map((q, i) => ({
            key: q.key,
            type: q.type,
            isCore: false,
            prompt: q.prompt,
            orderHint: 1000 + i,
            metadata: { scaleMax: q.scaleMax, scaleDimension: q.scaleDimension, dynamicFollowupCandidates: q.dynamicFollowupCandidates },
            options: {
              create: (q.options ?? []).map((o, j) => ({
                key: o.key,
                label: o.label,
                dimensionContributions: o.dimensionContributions,
                orderHint: j,
              })),
            },
          })),
        ],
      },
      adaptiveRules: {
        create: config.adaptiveRules.map((r) => ({ key: r.key, trigger: r.trigger as any, action: r.action as any, priority: r.priority })),
      },
      profiles: {
        create: config.profiles.map((p) => ({
          key: p.key,
          name: p.name,
          descriptionTemplate: p.descriptionTemplate,
          matchingRule: p.matchingRule as any,
        })),
      },
      reportTemplate: { create: { sections: config.premiumReportStructure as any } },
    },
  });

  await prisma.price.deleteMany({ where: { assessmentId } });
  for (const priceRef of Object.values(config.pricing)) {
    await prisma.price.create({
      data: { assessmentId, productType: priceRef.productType, amountCents: priceRef.amountCents, currency: priceRef.currency },
    });
  }

  await prisma.recommendationRule.deleteMany({ where: { fromAssessmentId: assessmentId } });
  for (const candidate of config.recommendedNext) {
    const toRow = await prisma.assessment.findUnique({ where: { slug: candidate.assessmentSlug } });
    if (!toRow) continue; // silently skip a recommendation pointing at a not-yet-existing slug
    await prisma.recommendationRule.create({
      data: {
        fromAssessmentId: assessmentId,
        toAssessmentId: toRow.id,
        condition: candidate.condition as any,
        weight: candidate.weight,
        bridgeCopy: candidate.bridgeCopy,
      },
    });
  }

  void assessment; // referenced above only to 404 early via findUniqueOrThrow
  return { versionId: version.id };
}

/** Publishes the current draft — the live app starts serving it on the very next request. */
export async function publishDraft(assessmentId: string): Promise<void> {
  const draft = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: null },
    orderBy: { versionNumber: "desc" },
  });
  if (!draft) throw new Error("No draft to publish — save one first");

  await prisma.$transaction([
    prisma.assessmentVersion.update({ where: { id: draft.id }, data: { publishedAt: new Date() } }),
    prisma.assessment.update({ where: { id: assessmentId }, data: { status: "published" } }),
  ]);
}
