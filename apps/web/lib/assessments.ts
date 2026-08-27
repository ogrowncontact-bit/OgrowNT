import { prisma } from "@inner/db";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { mapVersionToConfig, VERSION_INCLUDE } from "./catalogMapper";

/**
 * Public-facing loader — published versions only. This is the live source
 * of truth as of Phase 5; the static configs in @inner/content are seed
 * data only now (see prisma/seed.ts). This is what actually makes the
 * admin builder meaningful: a change saved there is live the next time
 * this function runs, no deploy involved.
 */
export async function getAssessmentConfig(slug: string): Promise<AssessmentConfig | null> {
  const assessment = await prisma.assessment.findUnique({ where: { slug } });
  if (!assessment || assessment.status !== "published") return null;

  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId: assessment.id, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
    include: VERSION_INCLUDE,
  });
  if (!version) return null;

  const [recommendations, prices] = await Promise.all([
    prisma.recommendationRule.findMany({ where: { fromAssessmentId: assessment.id }, include: { toAssessment: true } }),
    prisma.price.findMany({ where: { assessmentId: assessment.id, active: true } }),
  ]);

  // Admin emergency control (FASE 33) — a disabled question is excluded from
  // the live question bank here only, never from the admin editor's own
  // loader, so it stays visible (and re-enable-able) there.
  const activeVersion = { ...version, questions: version.questions.filter((q) => !q.disabledAt) };

  return mapVersionToConfig(assessment, activeVersion, recommendations, prices);
}

export async function listPublishedSlugs(): Promise<string[]> {
  const rows = await prisma.assessment.findMany({ where: { status: "published" }, select: { slug: true } });
  return rows.map((r) => r.slug);
}
