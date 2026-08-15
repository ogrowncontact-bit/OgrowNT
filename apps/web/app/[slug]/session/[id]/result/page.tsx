import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, Button } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

export default async function ResultPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const profileResult = await prisma.profileResult.findUnique({ where: { assessmentSessionId: id } });
  if (!profileResult) notFound();

  const primary = config.profiles.find((p) => p.key === profileResult.primaryProfileKey);
  if (!primary) notFound();

  const secondaryCount = (profileResult.secondaryProfileKeys as string[]).length;
  const lockedInsightCount = secondaryCount + config.premiumReportStructure.length - 1;

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
        <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
          {config.freeResultTemplate.insightIntro}
        </p>
        <p className="mt-4 flex items-center gap-2 text-sm font-medium text-[var(--inner-accent)]">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="shrink-0">
            <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2" />
          </svg>
          {lockedInsightCount} more insight{lockedInsightCount === 1 ? "" : "s"} in your full profile
        </p>
      </div>
    </Screen>
  );
}
