import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, Button } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";
import { formatPrice } from "@/lib/money";
import { getPremiumPreviewItems, TRUST_POINTS } from "@/lib/landingContent";

export default async function PaywallPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string; id: string }>;
  searchParams: Promise<{ payment?: string }>;
}) {
  const { slug, id } = await params;
  const { payment } = await searchParams;
  const paymentFailed = payment === "failed";

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const existingEntitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (existingEntitlement) redirect(`/${slug}/session/${id}/report`);

  const profileResult = await prisma.profileResult.findUnique({ where: { assessmentSessionId: id } });
  const primary = profileResult ? config.profiles.find((p) => p.key === profileResult.primaryProfileKey) : undefined;

  const price = config.pricing.individual;
  const previewItems = getPremiumPreviewItems(config);

  await track({
    anonymousSessionId,
    eventName: paymentFailed ? "payment_failed" : "paywall_viewed",
    assessmentId: session.assessmentId,
  });

  return (
    <Screen
      align="top"
      footer={
        <Link href={paymentFailed ? `/${slug}/session/${id}/checkout` : `/${slug}/session/${id}/report-preview`}>
          <Button>
            {paymentFailed
              ? "Try Again"
              : price
                ? `See a Preview — ${formatPrice(price.amountCents, price.currency)}`
                : "See a Preview"}
          </Button>
        </Link>
      }
    >
      {paymentFailed && (
        <div role="alert" className="mb-6 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[15px] font-medium text-[var(--inner-ink)]">Your payment wasn&apos;t completed.</p>
          <p className="mt-1 text-[13px] text-[var(--inner-ink-soft)]">
            Nothing was charged, and your answers are still saved — pick up right where you left off.
          </p>
        </div>
      )}

      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        Your Personal Report
      </p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Everything your answers revealed, in one place.
      </h1>

      {primary && (
        <div className="mt-6 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">What you already discovered</p>
          <p className="mt-2 text-[16px] font-medium text-[var(--inner-ink)]">{primary.name}</p>
          <p className="mt-1 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{primary.descriptionTemplate}</p>
        </div>
      )}

      <p className="mb-3 mt-8 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        What&apos;s still inside the full report
      </p>
      <ul className="space-y-3">
        {previewItems.map((item) => (
          <li key={item} className="flex items-start gap-3 text-[16px] text-[var(--inner-ink-soft)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" aria-hidden="true">
              <path
                d="M5 13l4 4L19 7"
                stroke="var(--inner-accent)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {item}
          </li>
        ))}
      </ul>

      <p className="mb-3 mt-8 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">A look inside</p>
      <div className="space-y-2">
        {config.premiumReportStructure.map((section) => (
          <div
            key={section.key}
            className="flex items-center gap-3 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] px-4 py-3 opacity-60"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="shrink-0 text-[var(--inner-muted)]">
              <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2" />
            </svg>
            <span className="text-[14px] text-[var(--inner-ink-soft)]">{section.title}</span>
          </div>
        ))}
      </div>

      <p className="mb-3 mt-8 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Privacy</p>
      <ul className="space-y-2">
        {TRUST_POINTS.map((point) => (
          <li key={point} className="text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
            {point}
          </li>
        ))}
      </ul>
    </Screen>
  );
}
