import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, LoadingState } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { selectRecommendation } from "@/lib/recommendation";
import { track } from "@/lib/analytics";
import { ReportPolling } from "@/components/ReportPolling";

interface ReportSection {
  key: string;
  title: string;
  body: string;
  aiGenerated: boolean;
}

export default async function ReportPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const currentAnonymousSessionId = await readAnonymousSessionId();
  const accessUserId = await readAccessUserId();
  if (!currentAnonymousSessionId && !accessUserId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id }, include: { anonymousSession: true } });
  if (!session) notFound();

  const ownsViaCurrentSession = currentAnonymousSessionId !== null && session.anonymousSessionId === currentAnonymousSessionId;
  const ownsViaMagicLink = accessUserId !== null && session.anonymousSession.userId === accessUserId;
  if (!ownsViaCurrentSession && !ownsViaMagicLink) notFound();

  // Attribute analytics/recommendation to the session's own anonymous session, not the
  // current browser's — when reached via magic link from a different device, there may
  // be no anonymous session cookie in this browser at all.
  const anonymousSessionId = session.anonymousSessionId;

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const entitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (!entitlement) redirect(`/${slug}/session/${id}/paywall`);

  // Computed from the assessment itself, not the report — available as soon as the
  // free result is, independent of whether report generation has finished.
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
  }

  const report = entitlement.reportId ? await prisma.report.findUnique({ where: { id: entitlement.reportId } }) : null;
  if (!report) {
    // Payment succeeded but generation is still in flight — expected under real
    // (non-mock) Stripe, where the browser lands here before the webhook that
    // runs completeOrder() is guaranteed to have processed. ReportPolling
    // refreshes this server component until the report shows up.
    return (
      <Screen align="top">
        <LoadingState
          eyebrow="One moment"
          title="Your INNER profile is being created."
          body="Your report will be delivered to your email — this page will update on its own."
        />
        {recommendation && <RecommendationCard recommendation={recommendation} />}
        <ReportPolling />
      </Screen>
    );
  }

  if (recommendation) {
    await track({ anonymousSessionId, eventName: "recommendation_viewed", assessmentId: session.assessmentId });
  }

  const content = report.content as unknown as { sections: ReportSection[] };

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        {config.name} — Full Report
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

      {recommendation && <RecommendationCard recommendation={recommendation} />}

      <p className="mb-12 text-center">
        <Link href="/explore" className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
          Explore all INNER experiences
        </Link>
      </p>
    </Screen>
  );
}

function RecommendationCard({ recommendation }: { recommendation: NonNullable<Awaited<ReturnType<typeof selectRecommendation>>> }) {
  return (
    <div className="mb-12 mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Next discovery</p>
      <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{recommendation.bridgeCopy}</p>
      <Link
        href={`/${recommendation.slug}`}
        className="mt-4 inline-block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-5 py-3 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
      >
        Explore {recommendation.name} →
      </Link>
    </div>
  );
}
