import { prisma } from "@inner/db";
import { getAssessmentConfig } from "@/lib/assessments";

export interface SessionRow {
  id: string;
  assessmentSlug: string;
  assessmentName: string;
  status: "in_progress" | "completed" | "abandoned";
  startedAt: Date;
  completedAt: Date | null;
  questionCount: number;
  primaryProfileName: string | null;
  /** Whether the free-tier insight/enrichment used a real AI call, or fell back to static template copy — never the content itself. */
  aiGenerated: boolean;
  purchased: boolean;
}

export interface SessionStatusCounts {
  inProgress: number;
  completed: number;
  abandoned: number;
  purchased: number;
}

/**
 * FASE 29 §ADMIN — visibility into assessment sessions (started, completed,
 * abandoned; profile result; whether AI ran) without ever surfacing raw
 * answer content. Deliberately separate from /admin/reports, which is
 * scoped to purchased Reports only — most sessions never reach that stage,
 * and the founder needs to see the funnel above the paywall too.
 */
export async function listSessionsForAdmin(limit = 100): Promise<SessionRow[]> {
  const sessions = await prisma.assessmentSession.findMany({
    orderBy: { startedAt: "desc" },
    take: limit,
    include: { assessment: true, profileResult: true, entitlements: { select: { id: true } } },
  });

  const configBySlug = new Map(
    await Promise.all([...new Set(sessions.map((s) => s.sourceSlug))].map(async (slug) => [slug, await getAssessmentConfig(slug)] as const))
  );

  return sessions.map((s): SessionRow => {
    const config = configBySlug.get(s.sourceSlug);
    const primary = s.profileResult ? config?.profiles.find((p) => p.key === s.profileResult!.primaryProfileKey) : undefined;
    const aiNotes = s.profileResult?.aiSemanticNotes as { aiGenerated?: boolean; enrichmentAiGenerated?: boolean } | null;
    return {
      id: s.id,
      assessmentSlug: s.sourceSlug,
      assessmentName: s.assessment.name,
      status: s.status,
      startedAt: s.startedAt,
      completedAt: s.completedAt,
      questionCount: s.questionCount,
      primaryProfileName: primary?.name ?? null,
      aiGenerated: Boolean(aiNotes?.aiGenerated || aiNotes?.enrichmentAiGenerated),
      purchased: s.entitlements.length > 0,
    };
  });
}

export async function getSessionStatusCounts(): Promise<SessionStatusCounts> {
  const [inProgress, completed, abandoned, purchased] = await Promise.all([
    prisma.assessmentSession.count({ where: { status: "in_progress" } }),
    prisma.assessmentSession.count({ where: { status: "completed" } }),
    prisma.assessmentSession.count({ where: { status: "abandoned" } }),
    prisma.entitlement.count(),
  ]);
  return { inProgress, completed, abandoned, purchased };
}
