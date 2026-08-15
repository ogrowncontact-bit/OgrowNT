import { PrismaClient } from "@prisma/client";
import { loveAssessment } from "@inner/content";
import { dimensionPool } from "@inner/content/dimensions";

const prisma = new PrismaClient();

async function main() {
  for (const dim of dimensionPool) {
    await prisma.dimension.upsert({
      where: { key: dim.key },
      update: { label: dim.label, description: dim.description },
      create: dim,
    });
  }

  const assessment = await prisma.assessment.upsert({
    where: { slug: loveAssessment.slug },
    update: {
      name: loveAssessment.name,
      category: loveAssessment.category,
      description: loveAssessment.description,
      hook: loveAssessment.hook,
      targetAudience: loveAssessment.targetAudience,
      status: "published",
    },
    create: {
      slug: loveAssessment.slug,
      name: loveAssessment.name,
      category: loveAssessment.category,
      description: loveAssessment.description,
      hook: loveAssessment.hook,
      targetAudience: loveAssessment.targetAudience,
      status: "published",
    },
  });

  const version = await prisma.assessmentVersion.create({
    data: {
      assessmentId: assessment.id,
      versionNumber: 1,
      minQuestions: loveAssessment.minQuestions,
      recommendedQuestions: loveAssessment.recommendedQuestions,
      maxQuestions: loveAssessment.maxQuestions,
      aiInfluenceCap: loveAssessment.scoringModel.aiInfluenceCap,
      publishedAt: new Date(),
      dimensions: {
        create: await Promise.all(
          loveAssessment.dimensions.map(async (d) => {
            const dim = await prisma.dimension.findUniqueOrThrow({ where: { key: d.key } });
            return { dimensionId: dim.id, weight: d.weight };
          })
        ),
      },
      questions: {
        create: [
          ...loveAssessment.questionBank.core.map((q, i) => ({
            key: q.key,
            type: q.type,
            isCore: true,
            prompt: q.prompt,
            orderHint: i,
            metadata: { scaleMax: q.scaleMax, scaleDimension: q.scaleDimension },
            options: {
              create: (q.options ?? []).map((o, j) => ({
                key: o.key,
                label: o.label,
                dimensionContributions: o.dimensionContributions,
                orderHint: j,
              })),
            },
          })),
          ...loveAssessment.questionBank.adaptivePool.map((q, i) => ({
            key: q.key,
            type: q.type,
            isCore: false,
            prompt: q.prompt,
            orderHint: 1000 + i,
            metadata: { scaleMax: q.scaleMax, scaleDimension: q.scaleDimension },
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
        create: loveAssessment.adaptiveRules.map((r) => ({
          key: r.key,
          trigger: r.trigger,
          action: r.action,
          priority: r.priority,
        })),
      },
      profiles: {
        create: loveAssessment.profiles.map((p) => ({
          key: p.key,
          name: p.name,
          descriptionTemplate: p.descriptionTemplate,
          matchingRule: p.matchingRule,
        })),
      },
      reportTemplate: {
        create: { sections: loveAssessment.premiumReportStructure },
      },
    },
  });

  for (const priceRef of Object.values(loveAssessment.pricing)) {
    await prisma.price.create({
      data: {
        assessmentId: assessment.id,
        productType: priceRef.productType,
        amountCents: priceRef.amountCents,
        currency: priceRef.currency,
      },
    });
  }

  console.log(`Seeded assessment "${assessment.slug}" (version ${version.versionNumber}).`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
