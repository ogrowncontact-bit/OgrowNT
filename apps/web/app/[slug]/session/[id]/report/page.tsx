import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, LoadingState } from "@inner/ui";
import type { ReportDocument } from "@inner/ai";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { selectRecommendation } from "@/lib/recommendation";
import { track } from "@/lib/analytics";
import { ReportPolling } from "@/components/ReportPolling";
import { RecommendationLink } from "@/components/RecommendationLink";
import { ReportView } from "@/components/ReportView";
import { ReportFeedbackForm } from "@/components/ReportFeedbackForm";
import { PurchaseFeedbackForm } from "@/components/PurchaseFeedbackForm";

export const metadata = { robots: { index: false, follow: false } };

export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string; id: string }>;
  searchParams: Promise<{ checkout?: string }>;
}) {
  const { slug, id } = await params;
  const { checkout } = await searchParams;

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
  if (!entitlement) {
    // No entitlement yet doesn't necessarily mean "never paid" — report
    // generation can fail *after* payment succeeds (an entitlement is only
    // ever created on the success path, see lib/commerce.ts). Redirecting a
    // paying customer back to the paywall would wrongly ask them to pay
    // again, so check for a durable failure record first.
    const failedReport = await prisma.report.findFirst({ where: { assessmentSessionId: id, status: "failed" } });
    if (failedReport) {
      return (
        <Screen align="top">
          <LoadingState
            eyebrow="One moment"
            title="We hit a problem preparing your report."
            body="Your payment went through — nothing was lost. We're on it, and this page will update automatically. If it's still stuck in a few minutes, contact support and we'll sort it out."
          />
          <p className="mt-6">
            <Link href="/support" className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
              Contact support
            </Link>
          </p>
          <ReportPolling />
        </Screen>
      );
    }
    redirect(`/${slug}/session/${id}/paywall`);
  }

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
        {recommendation && <RecommendationCard recommendation={recommendation} fromAssessmentId={session.assessmentId} />}
        <ReportPolling />
      </Screen>
    );
  }

  await track({
    anonymousSessionId,
    eventName: "report_viewed",
    assessmentId: session.assessmentId,
    properties: { reportId: report.id },
  });

  if (recommendation) {
    await track({ anonymousSessionId, eventName: "recommendation_viewed", assessmentId: session.assessmentId });
  }

  const document = report.content as unknown as ReportDocument;
  const existingFeedback = await prisma.reportFeedback.findUnique({ where: { reportId: report.id } });
  const existingPurchaseFeedback = await prisma.purchaseFeedback.findUnique({ where: { orderId: entitlement.orderId } });

  return (
    <Screen align="top">
      {checkout === "success" && !existingPurchaseFeedback && (
        <div className="mb-8">
          <PurchaseFeedbackForm orderId={entitlement.orderId} />
        </div>
      )}

      <a
        href={`/api/reports/${report.id}/pdf`}
        className="mb-6 inline-block rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-5 py-3 text-[15px] font-medium text-[var(--inner-ink)]"
      >
        Download PDF
      </a>

      <ReportView
        assessmentLabel={config.name}
        document={document}
        recommendationSlot={recommendation && <RecommendationCard recommendation={recommendation} fromAssessmentId={session.assessmentId} />}
      />

      {!existingFeedback && (
        <div className="mb-8">
          <ReportFeedbackForm reportId={report.id} />
        </div>
      )}

      <p className="mb-12 mt-12 text-center">
        <Link href="/explore" className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
          Explore all INNER experiences
        </Link>
      </p>
    </Screen>
  );
}

function RecommendationCard({
  recommendation,
  fromAssessmentId,
}: {
  recommendation: NonNullable<Awaited<ReturnType<typeof selectRecommendation>>>;
  fromAssessmentId: string;
}) {
  return (
    <div className="mb-12 mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Next discovery</p>
      <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{recommendation.bridgeCopy}</p>
      <RecommendationLink
        href={`/${recommendation.slug}`}
        fromAssessmentId={fromAssessmentId}
        toSlug={recommendation.slug}
        className="mt-4 inline-block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-5 py-3 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
      >
        Explore {recommendation.name} →
      </RecommendationLink>
    </div>
  );
}
