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
      shareTemplate: (config.shareTemplate as any) ?? undefined,
      tensionPairs: (config.tensionPairs as any) ?? undefined,
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
          priority: p.priority ?? 0,
        })),
      },
      reportTemplate: { create: { sections: config.premiumReportStructure as any } },
    },
  });

  // Deactivate rather than delete: a Price row is a required FK from any
  // historical Order that was ever charged against it (Order.priceId), so a
  // hard delete here would break the moment a real purchase exists (fine on
  // a config publish before launch, but not a safe pattern for production
  // republishing). `active: false` is exactly what checkout already filters
  // on when picking a price to charge.
  await prisma.price.updateMany({ where: { assessmentId, active: true }, data: { active: false } });
  for (const priceRef of Object.values(config.pricing)) {
    await prisma.price.create({
      data: { assessmentId, productType: priceRef.productType, amountCents: priceRef.amountCents, currency: priceRef.currency, active: true },
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

/**
 * Gate checked before a draft can go live — catches an assessment that
 * would be technically valid (passes validateAssessmentConfig's referential
 * checks) but practically unusable: no questions to ask, no profile it
 * could ever land on, no report to sell, no price to charge for it.
 * "Recommendation configured" is deliberately not a hard gate here — the
 * very first assessment ever published has nothing to point to yet.
 */
async function validatePublishReadiness(draftId: string, assessmentId: string): Promise<string[]> {
  const [draft, coreQuestionCount, profileCount, reportTemplate, activePriceCount] = await Promise.all([
    prisma.assessmentVersion.findUniqueOrThrow({ where: { id: draftId } }),
    prisma.question.count({ where: { assessmentVersionId: draftId, isCore: true } }),
    prisma.profile.count({ where: { assessmentVersionId: draftId } }),
    prisma.reportTemplate.findUnique({ where: { assessmentVersionId: draftId } }),
    prisma.price.count({ where: { assessmentId, active: true } }),
  ]);

  const problems: string[] = [];
  if (coreQuestionCount < draft.minQuestions) {
    problems.push(`needs at least ${draft.minQuestions} core questions (has ${coreQuestionCount})`);
  }
  if (profileCount === 0) problems.push("needs at least one profile");
  const reportSections = (reportTemplate?.sections as unknown[] | undefined) ?? [];
  if (reportSections.length === 0) problems.push("needs a premium report structure with at least one section");
  const freeResult = draft.freeResultTemplate as { headline?: string; insightIntro?: string } | null;
  if (!freeResult?.headline?.trim() || !freeResult?.insightIntro?.trim()) {
    problems.push("needs a free result headline and intro");
  }
  if (activePriceCount === 0) problems.push("needs at least one active price");

  return problems;
}

/** Publishes the current draft — the live app starts serving it on the very next request. */
export async function publishDraft(assessmentId: string): Promise<void> {
  const draft = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: null },
    orderBy: { versionNumber: "desc" },
  });
  if (!draft) throw new Error("No draft to publish — save one first");

  const problems = await validatePublishReadiness(draft.id, assessmentId);
  if (problems.length > 0) throw new Error(`Not ready to publish: ${problems.join("; ")}`);

  await prisma.$transaction([
    prisma.assessmentVersion.update({ where: { id: draft.id }, data: { publishedAt: new Date() } }),
    prisma.assessment.update({ where: { id: assessmentId }, data: { status: "published" } }),
  ]);
}

/**
 * Takes a live experience offline immediately without touching version
 * history — getAssessmentConfig() only ever serves a status="published"
 * assessment, so this alone is enough to stop the live app from serving
 * it. The already-published AssessmentVersion row is left untouched (its
 * publishedAt stays set), so republishAssessment() can bring it straight
 * back without going through save-draft again.
 */
export async function unpublishAssessment(assessmentId: string): Promise<void> {
  const assessment = await prisma.assessment.findUniqueOrThrow({ where: { id: assessmentId } });
  if (assessment.status !== "published") throw new Error(`Assessment is "${assessment.status}", not published`);
  await prisma.assessment.update({ where: { id: assessmentId }, data: { status: "draft" } });
}

/** Brings a merely-unpublished (not archived) experience back live, reusing its already-published version — no new draft cycle needed. */
export async function republishAssessment(assessmentId: string): Promise<void> {
  const hasPublishedVersion = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: { not: null } },
  });
  if (!hasPublishedVersion) throw new Error("No previously-published version to restore — publish a draft instead");
  await prisma.assessment.update({ where: { id: assessmentId }, data: { status: "published" } });
}

/** Permanent retirement — distinct from unpublish so an operator can tell "paused" from "done for good" in the list. */
export async function archiveAssessment(assessmentId: string): Promise<void> {
  await prisma.assessment.update({ where: { id: assessmentId }, data: { status: "archived" } });
}

/** Reopens an archived experience into draft — the normal edit/publish flow takes it from there. */
export async function restoreAssessment(assessmentId: string): Promise<void> {
  const assessment = await prisma.assessment.findUniqueOrThrow({ where: { id: assessmentId } });
  if (assessment.status !== "archived") throw new Error(`Assessment is "${assessment.status}", not archived`);
  await prisma.assessment.update({ where: { id: assessmentId }, data: { status: "draft" } });
}
