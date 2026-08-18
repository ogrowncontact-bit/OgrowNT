import { Suspense } from "react";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { Screen } from "@inner/ui";
import { BeginButton } from "@/components/BeginButton";
import { LandingViewTracker } from "@/components/LandingViewTracker";
import { getDiscoveryPoints, getFaqItems, TRUST_POINTS } from "@/lib/landingContent";
import { PublicNav } from "@/components/PublicNav";

const HOW_IT_WORKS = [
  "Answer a short, adaptive set of questions",
  "INNER identifies the meaningful patterns in your answers",
  "See your personalized result immediately",
  "Unlock the complete report if you want to go deeper",
];

/**
 * The one reusable template every /[slug] landing page renders through —
 * all copy beyond the assessment's own name/hook/description is generic
 * and identical across experiences, and the "what you'll discover" list
 * comes from the assessment's own real report structure (see
 * lib/landingContent.ts), not invented teaser copy.
 */
export function AssessmentLandingTemplate({ slug, config }: { slug: string; config: AssessmentConfig }) {
  const discoveryPoints = getDiscoveryPoints(config);
  const faqItems = getFaqItems(config);
  const price = config.pricing.individual;

  return (
    <Screen
      align="top"
      eyebrow={<PublicNav />}
      footer={
        <Suspense fallback={null}>
          <BeginButton slug={slug} />
        </Suspense>
      }
    >
      <Suspense fallback={null}>
        <LandingViewTracker slug={slug} />
      </Suspense>

      <h1 className="font-display text-[34px] leading-[1.15] text-[var(--inner-ink)]">{config.name}</h1>
      <p className="mt-5 text-[18px] leading-relaxed text-[var(--inner-ink-soft)]">{config.hook}</p>
      <p className="mt-6 text-sm text-[var(--inner-muted)]">
        About {config.recommendedQuestions} short questions · roughly 4–7 minutes · private, no account needed
      </p>

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

      {price && (
        <section className="mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6">
          <p className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">Complete report</p>
          <p className="font-display mt-2 text-[24px] text-[var(--inner-ink)]">
            {price.currency === "EUR" ? "€" : `${price.currency} `}
            {(price.amountCents / 100).toFixed(2)}
          </p>
          <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
            The free result gives you a short interpretation. The complete report goes deeper — a personalized, multi-section
            profile as a private web page and a downloadable PDF, both yours to keep.
          </p>
        </section>
      )}

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

      <section className="mb-8 mt-12">
        <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">
          Frequently asked
        </h2>
        <div className="mt-4 space-y-5">
          {faqItems.map((item) => (
            <div key={item.question}>
              <p className="text-[15px] font-medium text-[var(--inner-ink)]">{item.question}</p>
              <p className="mt-1 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{item.answer}</p>
            </div>
          ))}
        </div>
      </section>
    </Screen>
  );
}
