import { randomBytes, scryptSync } from "node:crypto";
import { PrismaClient } from "@prisma/client";
import { allAssessments, dimensionPool } from "@inner/content";
import type { AssessmentConfig } from "@inner/assessment-engine";

const prisma = new PrismaClient();

// Duplicated from apps/web/lib/security/password.ts (kept tiny + inline
// rather than adding a cross-package dependency just for this one script).
function hashPassword(password: string): string {
  const salt = randomBytes(16).toString("hex");
  const hash = scryptSync(password, salt, 64).toString("hex");
  return `${salt}:${hash}`;
}

/**
 * Creates version 1 of an assessment. Re-running this against a DB that
 * already has version 1 for the same slug will fail on the
 * (assessmentId, versionNumber) unique constraint — draft/republish
 * versioning is Phase 5 (admin) territory; for now this script is meant
 * for a fresh dev database.
 */
async function seedAssessment(assessment: AssessmentConfig) {
  const row = await prisma.assessment.upsert({
    where: { slug: assessment.slug },
    update: {
      name: assessment.name,
      category: assessment.category,
      description: assessment.description,
      hook: assessment.hook,
      targetAudience: assessment.targetAudience,
      status: "published",
    },
    create: {
      slug: assessment.slug,
      name: assessment.name,
      category: assessment.category,
      description: assessment.description,
      hook: assessment.hook,
      targetAudience: assessment.targetAudience,
      status: "published",
    },
  });

  const version = await prisma.assessmentVersion.create({
    data: {
      assessmentId: row.id,
      versionNumber: 1,
      minQuestions: assessment.minQuestions,
      recommendedQuestions: assessment.recommendedQuestions,
      maxQuestions: assessment.maxQuestions,
      aiInfluenceCap: assessment.scoringModel.aiInfluenceCap,
      freeResultTemplate: assessment.freeResultTemplate as any,
      publishedAt: new Date(),
      dimensions: {
        create: await Promise.all(
          assessment.dimensions.map(async (d) => {
            const dim = await prisma.dimension.findUniqueOrThrow({ where: { key: d.key } });
            return { dimensionId: dim.id, weight: d.weight };
          })
        ),
      },
      questions: {
        create: [
          ...assessment.questionBank.core.map((q, i) => ({
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
          ...assessment.questionBank.adaptivePool.map((q, i) => ({
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
        create: assessment.adaptiveRules.map((r) => ({
          key: r.key,
          trigger: r.trigger as any,
          action: r.action as any,
          priority: r.priority,
        })),
      },
      profiles: {
        create: assessment.profiles.map((p) => ({
          key: p.key,
          name: p.name,
          descriptionTemplate: p.descriptionTemplate,
          matchingRule: p.matchingRule as any,
        })),
      },
      reportTemplate: {
        create: { sections: assessment.premiumReportStructure as any },
      },
    },
  });

  await prisma.price.deleteMany({ where: { assessmentId: row.id } });
  for (const priceRef of Object.values(assessment.pricing)) {
    await prisma.price.create({
      data: {
        assessmentId: row.id,
        productType: priceRef.productType,
        amountCents: priceRef.amountCents,
        currency: priceRef.currency,
      },
    });
  }

  console.log(`Seeded assessment "${row.slug}" (version ${version.versionNumber}).`);
}

async function main() {
  for (const dim of dimensionPool) {
    await prisma.dimension.upsert({
      where: { key: dim.key },
      update: { label: dim.label, description: dim.description },
      create: dim,
    });
  }

  for (const assessment of allAssessments) {
    await seedAssessment(assessment);
  }

  // Second pass: recommendedNext references other assessments by slug, so
  // this can only run once every assessment row already exists.
  for (const assessment of allAssessments) {
    const fromRow = await prisma.assessment.findUniqueOrThrow({ where: { slug: assessment.slug } });
    await prisma.recommendationRule.deleteMany({ where: { fromAssessmentId: fromRow.id } });
    for (const candidate of assessment.recommendedNext) {
      const toRow = await prisma.assessment.findUnique({ where: { slug: candidate.assessmentSlug } });
      if (!toRow) {
        console.warn(`Skipping recommendation ${assessment.slug} -> ${candidate.assessmentSlug}: target not seeded`);
        continue;
      }
      await prisma.recommendationRule.create({
        data: {
          fromAssessmentId: fromRow.id,
          toAssessmentId: toRow.id,
          condition: candidate.condition as any,
          weight: candidate.weight,
          bridgeCopy: candidate.bridgeCopy,
        },
      });
    }
  }
  console.log("Seeded recommendation graph.");

  const adminEmail = (process.env.ADMIN_EMAIL ?? "admin@inner.dev").toLowerCase();
  const adminPassword = process.env.ADMIN_PASSWORD ?? "changeme-dev-only";
  await prisma.adminUser.upsert({
    where: { email: adminEmail },
    update: {},
    create: { email: adminEmail, passwordHash: hashPassword(adminPassword), role: "owner" },
  });
  console.log(
    `Seeded admin user "${adminEmail}"${process.env.ADMIN_PASSWORD ? "" : " with the dev-only default password — set ADMIN_EMAIL/ADMIN_PASSWORD env vars before seeding a real environment"}.`
  );
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
