import { prisma } from "@inner/db";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { mapVersionToConfig, VERSION_INCLUDE } from "../catalogMapper";

export interface AdminAssessmentListItem {
  id: string;
  slug: string;
  name: string;
  status: "draft" | "published" | "archived";
  hasDraft: boolean;
  publishedVersion: number | null;
}

export async function listAssessmentsForAdmin(): Promise<AdminAssessmentListItem[]> {
  const assessments = await prisma.assessment.findMany({
    orderBy: { name: "asc" },
    include: { versions: { select: { versionNumber: true, publishedAt: true } } },
  });

  return assessments.map((a) => {
    const published = a.versions.filter((v) => v.publishedAt).sort((x, y) => y.versionNumber - x.versionNumber)[0];
    const hasDraft = a.versions.some((v) => !v.publishedAt);
    return {
      id: a.id,
      slug: a.slug,
      name: a.name,
      status: a.status,
      hasDraft,
      publishedVersion: published?.versionNumber ?? null,
    };
  });
}

/**
 * Loads whatever an admin should see when opening the builder: the draft
 * version if one exists (most recent edits, possibly unpublished), else
 * the latest published version as a starting point.
 */
export async function loadAssessmentForEdit(
  assessmentId: string
): Promise<{ config: AssessmentConfig; hasDraft: boolean } | null> {
  const assessment = await prisma.assessment.findUnique({ where: { id: assessmentId } });
  if (!assessment) return null;

  const draft = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: null },
    orderBy: { versionNumber: "desc" },
    include: VERSION_INCLUDE,
  });
  const version =
    draft ??
    (await prisma.assessmentVersion.findFirst({
      where: { assessmentId, publishedAt: { not: null } },
      orderBy: { versionNumber: "desc" },
      include: VERSION_INCLUDE,
    }));
  if (!version) return null;

  const [recommendations, prices] = await Promise.all([
    prisma.recommendationRule.findMany({ where: { fromAssessmentId: assessmentId }, include: { toAssessment: true } }),
    prisma.price.findMany({ where: { assessmentId } }),
  ]);

  return { config: mapVersionToConfig(assessment, version, recommendations, prices), hasDraft: !!draft };
}
