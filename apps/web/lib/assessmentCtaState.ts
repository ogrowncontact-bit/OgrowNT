import { prisma } from "@inner/db";

/**
 * Drives the CTA spec's "CTA Logic" section — what a returning visitor's
 * primary button should say and link to, for one specific assessment.
 * Reuses the exact same AssessmentSession/Entitlement lookups the
 * checkout/paywall/report pages already do (see
 * app/[slug]/session/[id]/{checkout,paywall,report}/page.tsx) rather than
 * inventing a second way to determine "has this been purchased."
 */
export type AssessmentCtaKind = "start" | "continue" | "view_result" | "open_report";

export interface AssessmentCtaState {
  kind: AssessmentCtaKind;
  href: string;
}

export async function getAssessmentCtaState(params: { anonymousSessionId: string | null; slug: string; assessmentId: string }): Promise<AssessmentCtaState> {
  if (!params.anonymousSessionId) {
    return { kind: "start", href: `/${params.slug}` };
  }

  const latestSession = await prisma.assessmentSession.findFirst({
    where: { anonymousSessionId: params.anonymousSessionId, assessmentId: params.assessmentId },
    orderBy: { startedAt: "desc" },
  });

  if (!latestSession) return { kind: "start", href: `/${params.slug}` };

  if (latestSession.status === "in_progress") {
    return { kind: "continue", href: `/${params.slug}/session/${latestSession.id}` };
  }

  if (latestSession.status === "completed") {
    const entitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: latestSession.id } });
    if (entitlement) {
      return { kind: "open_report", href: `/${params.slug}/session/${latestSession.id}/report` };
    }
    return { kind: "view_result", href: `/${params.slug}/session/${latestSession.id}/result` };
  }

  // abandoned — treat like a fresh start rather than resuming a dead session.
  return { kind: "start", href: `/${params.slug}` };
}

export const CTA_LABELS: Record<AssessmentCtaKind, string> = {
  start: "Start Discovery",
  continue: "Continue Discovery",
  view_result: "View Result",
  open_report: "Open Report",
};
