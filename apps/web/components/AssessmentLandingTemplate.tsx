import { Suspense } from "react";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { Screen } from "@inner/ui";
import { LandingViewTracker } from "@/components/LandingViewTracker";
import { getDiscoveryPoints, getFaqItems, getPremiumPreviewItems, TRUST_POINTS, type LandingContentOverrides } from "@/lib/landingContent";
import type { AssessmentCtaState } from "@/lib/assessmentCtaState";
import { PublicNav } from "@/components/PublicNav";
import { ExampleInsight } from "@/components/landing/ExampleInsight";
import { FaqAccordion } from "@/components/landing/FaqAccordion";
import { PremiumReportPreview } from "@/components/landing/PremiumReportPreview";
import { AssessmentCTA } from "@/components/landing/AssessmentCTA";
import { ScrollDepthTracker } from "@/components/landing/ScrollDepthTracker";

const HOW_IT_WORKS = [
  "Answer a short, adaptive set of questions",
  "INNER identifies the meaningful patterns in your answers",
  "See your personalized result immediately",
  "Unlock the complete report if you want to go deeper",
];

interface Props {
  slug: string;
  assessmentId: string;
  config: AssessmentConfig;
  landingContent: LandingContentOverrides;
  ctaState: AssessmentCtaState;
}

/**
 * The one reusable template every /[slug] landing page renders through
 * (FASE 23 §LANDING STRUCTURE, 9 sections) — all copy beyond the
 * assessment's own real data is either generic-and-identical across
 * experiences, or admin-editable CMS copy (lib/landingContent.ts's
 * LandingContentOverrides) with a code-level fallback, never fabricated.
 */
export function AssessmentLandingTemplate({ slug, assessmentId, config, landingContent, ctaState }: Props) {
  const discoveryPoints = getDiscoveryPoints(config);
  const faqItems = getFaqItems(config, landingContent.extraFaqItems);
  const premiumPreviewItems = getPremiumPreviewItems(config);
  const price = config.pricing.individual;
  const headline = landingContent.headline?.trim() || config.name;
  const subheadline = landingContent.subheadline?.trim() || config.hook;

  return (
    <Screen
      align="top"
      eyebrow={<PublicNav />}
      footer={
        <Suspense fallback={null}>
          <AssessmentCTA slug={slug} ctaState={ctaState} label={landingContent.ctaLabel ?? undefined} />
        </Suspense>
      }
    >
      <Suspense fallback={null}>
        <LandingViewTracker slug={slug} />
      </Suspense>
      <ScrollDepthTracker slug={slug} />

      {/* SECTION 1 — Hero */}
      <h1 className="font-display text-[34px] leading-[1.15] text-[var(--inner-ink)]">{headline}</h1>
      <p className="mt-5 text-[18px] leading-relaxed text-[var(--inner-ink-soft)]">{subheadline}</p>
      <p className="mt-6 text-sm text-[var(--inner-muted)]">
        About {config.recommendedQuestions} short questions · roughly 4–7 minutes · private, no account needed
      </p>

      {/* SECTION 2 — Curiosity Hook */}
      {landingContent.curiosityHook?.trim() && (
        <section className="mt-10 border-l-2 border-[var(--inner-accent)] pl-4">
          <p className="text-[16px] italic leading-relaxed text-[var(--inner-ink)]">{landingContent.curiosityHook}</p>
        </section>
      )}

      {/* SECTION 3 — What You'll Discover */}
      {discoveryPoints.length > 0 && (
        <section className="mt-12">
          <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">
            What you'll discover
          </h2>
          <ul className="mt-4 space-y-3">
            {discoveryPoints.map((point) => (
              <li key={point.title} className="flex items-start gap-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
                <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--inner-accent)]" />
                {point.title}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* SECTION 4 — How It Works */}
      <section className="mt-12">
        <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">How it works</h2>
        <ol className="mt-4 space-y-3">
          {HOW_IT_WORKS.map((step, i) => (
            <li key={step} className="flex items-start gap-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
              <span
                aria-hidden
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--inner-card)] text-[11px] font-medium text-[var(--inner-ink)]"
              >
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      {/* SECTION 5 — Example Insight */}
      {landingContent.exampleInsight?.trim() && <ExampleInsight text={landingContent.exampleInsight} />}

      {/* SECTION 6 — Premium Report Preview */}
      {price && (
        <PremiumReportPreview
          items={premiumPreviewItems}
          priceCents={price.amountCents}
          currency={price.currency}
          assessmentId={assessmentId}
        />
      )}

      {/* SECTION 7 — Privacy & Trust */}
      <section className="mt-12">
        <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">Privacy</h2>
        <ul className="mt-4 space-y-2">
          {TRUST_POINTS.map((point) => (
            <li key={point} className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
              {point}
            </li>
          ))}
        </ul>
      </section>

      {/* SECTION 8 — FAQ */}
      <section className="mt-12">
        <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">
          Frequently asked
        </h2>
        <FaqAccordion items={faqItems} assessmentId={assessmentId} />
      </section>

      {/* SECTION 9 — Final CTA */}
      <section className="mb-8 mt-14 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-paper-dim)] p-6 text-center">
        <p className="font-display text-[19px] text-[var(--inner-ink)]">Ready to see your pattern?</p>
        <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
          A few minutes, no account needed — your free result is waiting on the other side.
        </p>
        <div className="mt-5">
          <Suspense fallback={null}>
            <AssessmentCTA slug={slug} ctaState={ctaState} label={landingContent.ctaLabel ?? undefined} />
          </Suspense>
        </div>
      </section>
    </Screen>
  );
}
