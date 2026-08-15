import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Screen } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { BeginButton } from "@/components/BeginButton";
import { LandingViewTracker } from "@/components/LandingViewTracker";

export default async function ExperienceLanding({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const config = getAssessmentConfig(slug);
  if (!config) notFound();

  return (
    <Screen
      footer={
        <Suspense fallback={null}>
          <BeginButton slug={slug} />
        </Suspense>
      }
    >
      <Suspense fallback={null}>
        <LandingViewTracker slug={slug} />
      </Suspense>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">INNER</p>
      <h1 className="font-display text-[34px] leading-[1.15] text-[var(--inner-ink)]">{config.name}</h1>
      <p className="mt-5 text-[18px] leading-relaxed text-[var(--inner-ink-soft)]">{config.hook}</p>
      <p className="mt-8 text-sm text-[var(--inner-muted)]">
        About {config.recommendedQuestions} short questions · roughly 4–7 minutes · private, no account needed
      </p>
    </Screen>
  );
}
