import { prisma } from "@inner/db";
import { dimensionPool } from "@inner/content/dimensions";
import { getAssessmentConfig } from "./assessments";
import {
  aggregateDimension,
  buildInsights,
  type MasterProfileDimension,
  type MasterProfileDimensionReading,
  type MasterProfileInsight,
} from "./masterProfileInsights";

export type { MasterProfileDimension, MasterProfileDimensionReading, MasterProfileInsight } from "./masterProfileInsights";

/**
 * Cross-assessment aggregation — the "Master Profile" foundation. This
 * leans entirely on the fact that dimension keys are a shared global pool
 * (packages/content/src/dimensions.ts): a "connection" score from LOVE and
 * a "connection" score from Jealousy are already directly comparable, no
 * meaning-level identity resolution needed. The only identity resolution
 * required is *person*-level — see resolveAnonymousSessionIds. The actual
 * averaging/divergence/narration math lives in lib/masterProfileInsights.ts
 * so it's unit-testable without a live Postgres connection.
 */

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

export interface CompletedAssessmentSummary {
  slug: string;
  name: string;
  primaryProfileName: string | null;
  completedAt: Date;
}

export interface MasterProfile {
  completedAssessments: CompletedAssessmentSummary[];
  dimensions: MasterProfileDimension[];
  insights: MasterProfileInsight[];
}

export interface Identity {
  anonymousSessionId?: string | null;
  accessUserId?: string | null;
}

/** Every anonymous session id that plausibly belongs to the same person: the current browser's, plus — when authenticated via magic link — every device ever linked to that account. */
async function resolveAnonymousSessionIds(identity: Identity): Promise<string[]> {
  const ids = new Set<string>();
  if (identity.anonymousSessionId) ids.add(identity.anonymousSessionId);
  if (identity.accessUserId) {
    const linked = await prisma.anonymousSession.findMany({
      where: { userId: identity.accessUserId },
      select: { id: true },
    });
    for (const row of linked) ids.add(row.id);
  }
  return [...ids];
}

/**
 * Returns null when there's nothing to aggregate (fewer than 2 completed
 * assessments) — a "master profile" of one assessment is just that
 * assessment's own report, nothing new to say.
 */
export async function getMasterProfile(identity: Identity): Promise<MasterProfile | null> {
  const anonymousSessionIds = await resolveAnonymousSessionIds(identity);
  if (anonymousSessionIds.length === 0) return null;

  const sessions = await prisma.assessmentSession.findMany({
    where: { anonymousSessionId: { in: anonymousSessionIds }, status: "completed" },
    include: { assessment: true, profileResult: true, dimensionScores: true },
    orderBy: { completedAt: "desc" },
  });

  // A retake shouldn't double-weight a dimension — only the most recent
  // completion per assessment counts toward the master profile.
  const latestPerAssessment = new Map<string, (typeof sessions)[number]>();
  for (const session of sessions) {
    if (!latestPerAssessment.has(session.assessmentId)) latestPerAssessment.set(session.assessmentId, session);
  }
  const uniqueSessions = [...latestPerAssessment.values()];
  if (uniqueSessions.length < 2) return null;

  const configsBySlug = new Map(
    await Promise.all(
      uniqueSessions.map(async (s) => [s.assessment.slug, await getAssessmentConfig(s.assessment.slug)] as const)
    )
  );

  const completedAssessments: CompletedAssessmentSummary[] = uniqueSessions.map((s) => {
    const config = configsBySlug.get(s.assessment.slug);
    const primary = config?.profiles.find((p) => p.key === s.profileResult?.primaryProfileKey);
    return {
      slug: s.assessment.slug,
      name: s.assessment.name,
      primaryProfileName: primary?.name ?? null,
      completedAt: s.completedAt ?? s.startedAt,
    };
  });

  const readingsByDimension = new Map<string, MasterProfileDimensionReading[]>();
  for (const s of uniqueSessions) {
    for (const d of s.dimensionScores) {
      const list = readingsByDimension.get(d.dimensionKey) ?? [];
      list.push({ slug: s.assessment.slug, assessmentName: s.assessment.name, score: d.normalizedScore, confidence: d.confidence });
      readingsByDimension.set(d.dimensionKey, list);
    }
  }

  const dimensions = [...readingsByDimension.entries()]
    // Only dimensions actually shared across 2+ completed assessments say
    // anything cross-assessment — a dimension only one assessment touched
    // belongs to that assessment's own report, not here.
    .filter(([, readings]) => readings.length >= 2)
    .map(([key, readings]) => aggregateDimension(key, dimensionLabels[key] ?? key, readings))
    .sort((a, b) => b.averageScore - a.averageScore);

  return { completedAssessments, dimensions, insights: buildInsights(dimensions) };
}
