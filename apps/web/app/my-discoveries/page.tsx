import Link from "next/link";
import type { Metadata } from "next";
import { Screen } from "@inner/ui";
import { prisma } from "@inner/db";
import { getAssessmentConfig, listPublishedSlugs } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { rankExploreCandidates } from "@/lib/explorePersonalization";
import { CTA_LABELS, type AssessmentCtaKind } from "@/lib/assessmentCtaState";
import { PublicNav } from "@/components/PublicNav";

export const metadata: Metadata = {
  title: "My Discoveries",
  description: "Your INNER journey so far — what you've discovered, and what's next.",
  robots: { index: false, follow: false },
};

// Always reflects this browser's live session state (mirrors /explore's own
// reasoning) — never safe to statically prerender.
export const dynamic = "force-dynamic";

interface DiscoveryRow {
  slug: string;
  name: string;
  hook: string;
  kind: AssessmentCtaKind;
  href: string;
  reportId?: string;
}

export default async function MyDiscoveriesPage() {
  const anonymousSessionId = await readAnonymousSessionId();

  let discoveries: DiscoveryRow[] = [];
  let recommended: { slug: string; name: string; hook: string } | null = null;

  if (anonymousSessionId) {
    const sessions = await prisma.assessmentSession.findMany({
      where: { anonymousSessionId },
      orderBy: { startedAt: "desc" },
      include: { assessment: true },
    });

    // One row per discovery — the most recent session already sorts first,
    // so the first occurrence of an assessmentId is its latest attempt.
    const latestByAssessment = new Map<string, (typeof sessions)[number]>();
    for (const s of sessions) {
      if (!latestByAssessment.has(s.assessmentId)) latestByAssessment.set(s.assessmentId, s);
    }

    const completedIds = [...latestByAssessment.values()].filter((s) => s.status === "completed").map((s) => s.id);
    const entitlements = completedIds.length
      ? await prisma.entitlement.findMany({ where: { assessmentSessionId: { in: completedIds } } })
      : [];
    const reportIdBySessionId = new Map(entitlements.filter((e) => e.reportId).map((e) => [e.assessmentSessionId, e.reportId!]));

    discoveries = [...latestByAssessment.values()].map((s): DiscoveryRow => {
      if (s.status === "in_progress") {
        return { slug: s.sourceSlug, name: s.assessment.name, hook: s.assessment.hook, kind: "continue", href: `/${s.sourceSlug}/session/${s.id}` };
      }
      if (s.status === "completed") {
        const reportId = reportIdBySessionId.get(s.id);
        if (reportId) {
          return {
            slug: s.sourceSlug,
            name: s.assessment.name,
            hook: s.assessment.hook,
            kind: "open_report",
            href: `/${s.sourceSlug}/session/${s.id}/report`,
            reportId,
          };
        }
        return { slug: s.sourceSlug, name: s.assessment.name, hook: s.assessment.hook, kind: "view_result", href: `/${s.sourceSlug}/session/${s.id}/result` };
      }
      // abandoned — offer a fresh start rather than resuming a dead session.
      return { slug: s.sourceSlug, name: s.assessment.name, hook: s.assessment.hook, kind: "start", href: `/${s.sourceSlug}` };
    });

    const publishedSlugs = await listPublishedSlugs();
    const ranked = await rankExploreCandidates({ anonymousSessionId, publishedSlugs });
    const topCandidate = ranked.find((r) => !r.completed && r.relevanceScore > 0);
    if (topCandidate) {
      const config = await getAssessmentConfig(topCandidate.slug);
      if (config) recommended = { slug: config.slug, name: config.name, hook: config.hook };
    }
  }

  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Your journey</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">Your Discoveries</h1>

      {discoveries.length === 0 ? (
        <div className="mt-8">
          <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
            You haven&apos;t started a discovery yet. Every INNER experience takes a few quiet minutes and reveals a real
            pattern in how you connect, decide, or express yourself.
          </p>
          <Link
            href="/explore"
            className="mt-6 inline-block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-5 py-3 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
          >
            Explore INNER experiences →
          </Link>
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {discoveries.map((d) => (
            <div key={d.slug} className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
              <Link href={d.href} className="block">
                <p className="text-[11px] font-medium uppercase tracking-[0.15em] text-[var(--inner-accent)]">
                  {d.kind === "continue" ? "In progress" : d.kind === "start" ? "Not finished" : "Completed"}
                </p>
                <h2 className="font-display mt-1 text-[19px] text-[var(--inner-ink)]">{d.name}</h2>
                <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{d.hook}</p>
                <p className="mt-3 text-[13px] font-medium text-[var(--inner-ink)]">{CTA_LABELS[d.kind]} →</p>
              </Link>
              {d.reportId && (
                <a
                  href={`/api/reports/${d.reportId}/pdf`}
                  className="mt-3 inline-block text-[13px] font-medium text-[var(--inner-muted)] underline underline-offset-4"
                >
                  Download PDF
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {recommended && (
        <div className="mt-8 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] p-5">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Recommended next</p>
          <h2 className="font-display mt-1 text-[19px] text-[var(--inner-ink)]">{recommended.name}</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{recommended.hook}</p>
          <Link href={`/${recommended.slug}`} className="mt-3 inline-block text-[13px] font-medium text-[var(--inner-accent)]">
            Explore {recommended.name} →
          </Link>
        </div>
      )}

      <p className="mb-12 mt-12">
        <Link href="/explore" className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
          See every INNER experience
        </Link>
      </p>
    </Screen>
  );
}
