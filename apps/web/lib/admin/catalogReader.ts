import { prisma } from "@inner/db";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { mapVersionToConfig, VERSION_INCLUDE } from "../catalogMapper";

export interface AdminAssessmentListItem {
  id: string;
  slug: string;
  name: string;
  category: string;
  status: "draft" | "published" | "archived";
  hasDraft: boolean;
  hasPublishedVersion: boolean;
  publishedVersion: number | null;
  completions: number;
  priceLabel: string | null;
  updatedAt: Date;
}

export async function listAssessmentsForAdmin(): Promise<AdminAssessmentListItem[]> {
  const assessments = await prisma.assessment.findMany({
    orderBy: { name: "asc" },
    include: {
      versions: { select: { versionNumber: true, publishedAt: true } },
      prices: { where: { active: true, productType: "individual" }, select: { amountCents: true, currency: true } },
      _count: { select: { assessmentSessions: { where: { status: "completed" } } } },
    },
  });

  return assessments.map((a) => {
    const published = a.versions.filter((v) => v.publishedAt).sort((x, y) => y.versionNumber - x.versionNumber)[0];
    const hasDraft = a.versions.some((v) => !v.publishedAt);
    const activePrice = a.prices[0];
    return {
      id: a.id,
      slug: a.slug,
      name: a.name,
      category: a.category,
      status: a.status,
      hasDraft,
      hasPublishedVersion: !!published,
      publishedVersion: published?.versionNumber ?? null,
      completions: a._count.assessmentSessions,
      priceLabel: activePrice
        ? new Intl.NumberFormat("en-IE", { style: "currency", currency: activePrice.currency }).format(activePrice.amountCents / 100)
        : null,
      updatedAt: a.updatedAt,
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

export interface AssessmentVersionSummary {
  id: string;
  versionNumber: number;
  publishedAt: Date | null;
  createdAt: Date;
}

/** Every publish snapshots a new AssessmentVersion row (docs/ARCHITECTURE.md §10) — this just makes that existing history visible. */
export async function listVersionHistory(assessmentId: string): Promise<AssessmentVersionSummary[]> {
  const versions = await prisma.assessmentVersion.findMany({
    where: { assessmentId },
    orderBy: { versionNumber: "desc" },
    select: { id: true, versionNumber: true, publishedAt: true, createdAt: true },
  });
  return versions;
}
