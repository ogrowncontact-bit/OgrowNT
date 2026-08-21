import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, Button } from "@inner/ui";
import { dimensionPool } from "@inner/content/dimensions";
import type { EnrichedInsight } from "@inner/ai";
import type { TensionResult } from "@inner/assessment-engine";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";
import { ShareResultButton } from "@/components/ShareResultButton";
import { buildFreeReflectionQuestion } from "@/lib/freeResultContent";

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

export default async function ResultPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const profileResult = await prisma.profileResult.findUnique({ where: { assessmentSessionId: id } });
  if (!profileResult) notFound();

  const primary = config.profiles.find((p) => p.key === profileResult.primaryProfileKey);
  if (!primary) notFound();

  const secondaryCount = (profileResult.secondaryProfileKeys as string[]).length;
  const lockedInsightCount = secondaryCount + config.premiumReportStructure.length - 1;

  // Profile AI's narration of the already-decided profile, when available (Phase 2) —
  // falls back to the assessment's static template copy otherwise. AI is never the
  // only source of this screen's content. See docs/ARCHITECTURE.md §6.
  const aiNotes = profileResult.aiSemanticNotes as { insight?: string; aiGenerated?: boolean; insights?: EnrichedInsight[] } | null;
  const insightText = aiNotes?.insight || config.freeResultTemplate.insightIntro;
  const observations = (aiNotes?.insights ?? []).slice(0, 3);

  const tensions = (profileResult.tensions as TensionResult[] | null) ?? [];
  const topTension = [...tensions].sort((a, b) => b.strength - a.strength)[0];

  const dimensionScoreRows = await prisma.dimensionScore.findMany({ where: { assessmentSessionId: id } });
  const topDimension = [...dimensionScoreRows].sort((a, b) => b.normalizedScore - a.normalizedScore)[0];
  const topDimensionLabel = topDimension ? (dimensionLabels[topDimension.dimensionKey] ?? topDimension.dimensionKey) : primary.name;

  const reflectionQuestion = buildFreeReflectionQuestion(topDimensionLabel, topTension?.label);

  const shareTitle = config.shareTemplate?.shareTitleTemplate ?? "I discovered my INNER profile:";
  const shareText = (config.shareTemplate?.shareTextTemplate ?? "I discovered my INNER profile: {{profileName}}. Discover yours.").replace(
    "{{profileName}}",
    primary.name
  );

  await track({ anonymousSessionId, eventName: "free_result_viewed", assessmentId: session.assessmentId });

  return (
    <Screen
      align="top"
      footer={
        <Link href={`/${slug}/session/${id}/paywall`}>
          <Button>Unlock My Full Profile</Button>
        </Link>
      }
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        {config.freeResultTemplate.headline}
      </p>
      <h1 className="font-display text-[30px] leading-tight text-[var(--inner-ink)]">{primary.name}</h1>
      <p className="mt-5 text-[17px] leading-relaxed text-[var(--inner-ink-soft)]">{primary.descriptionTemplate}</p>

      <div className="mt-8 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
        <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{insightText}</p>
      </div>

      {observations.length > 0 && (
        <div className="mt-6">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">What we noticed</p>
          <ul className="space-y-3">
            {observations.map((observation, i) => (
              <li key={i} className="flex items-start gap-3">
                <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--inner-accent)]" />
                <span className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{observation.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {topTension && (
        <div className="mt-6 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">A tension worth noticing</p>
          <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{topTension.label}</p>
        </div>
      )}

      <div className="mt-6 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] p-5">
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">A question to sit with</p>
        <p className="text-[16px] italic leading-relaxed text-[var(--inner-ink)]">{reflectionQuestion}</p>
      </div>

      <p className="mt-6 flex items-center gap-2 text-sm font-medium text-[var(--inner-accent)]">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="shrink-0">
          <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="2" />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2" />
        </svg>
        {lockedInsightCount} more insight{lockedInsightCount === 1 ? "" : "s"} in your full profile
      </p>

      <div className="mt-4">
        <ShareResultButton shareTitle={shareTitle} shareText={shareText} />
      </div>
    </Screen>
  );
}
