import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { selectRecommendation } from "@/lib/recommendation";
import { track } from "@/lib/analytics";

interface ReportSection {
  key: string;
  title: string;
  body: string;
  aiGenerated: boolean;
}

export default async function ReportPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const entitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (!entitlement) redirect(`/${slug}/session/${id}/paywall`);

  const report = entitlement.reportId ? await prisma.report.findUnique({ where: { id: entitlement.reportId } }) : null;
  if (!report) {
    // Payment succeeded but generation is still in flight (or failed) — this
    // stays synchronous in Phase 3, so in practice this only shows briefly.
    return (
      <Screen>
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">One moment</p>
        <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">
          We&apos;re still preparing your profile — refresh in a few seconds.
        </h1>
      </Screen>
    );
  }

  const content = report.content as unknown as { sections: ReportSection[] };
  const profileResult = await prisma.profileResult.findUnique({ where: { assessmentSessionId: id } });
  const primary = config.profiles.find((p) => p.key === profileResult?.primaryProfileKey);

  let recommendation: Awaited<ReturnType<typeof selectRecommendation>> = null;
  if (primary) {
    const dimensionScoreRows = await prisma.dimensionScore.findMany({ where: { assessmentSessionId: id } });
    recommendation = await selectRecommendation({
      anonymousSessionId,
      fromConfig: config,
      primaryProfileName: primary.name,
      dimensionScores: Object.fromEntries(dimensionScoreRows.map((d) => [d.dimensionKey, d.normalizedScore])),
    });
    if (recommendation) {
      await track({ anonymousSessionId, eventName: "recommendation_viewed", assessmentId: session.assessmentId });
    }
  }

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        Your {config.name} Report
      </p>
      <h1 className="font-display text-[30px] leading-tight text-[var(--inner-ink)]">{primary?.name}</h1>

      <a
        href={`/api/reports/${report.id}/pdf`}
        className="mt-6 inline-block rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-5 py-3 text-[15px] font-medium text-[var(--inner-ink)]"
      >
        Download PDF
      </a>

      <div className="mt-10 space-y-8">
        {content.sections.map((section) => (
          <div key={section.key}>
            <h2 className="font-display text-[19px] text-[var(--inner-accent)]">{section.title}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{section.body}</p>
          </div>
        ))}
      </div>

      {recommendation && (
        <div className="mb-12 mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6">
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
            Next discovery
          </p>
          <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{recommendation.bridgeCopy}</p>
          <Link
            href={`/${recommendation.slug}`}
            className="mt-4 inline-block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-5 py-3 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
          >
            Explore {recommendation.name} →
          </Link>
        </div>
      )}

      <p className="mb-12 text-center">
        <Link href="/explore" className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
          Explore all INNER experiences
        </Link>
      </p>
    </Screen>
  );
}
