import Link from "next/link";
import { Screen } from "@inner/ui";
import { getAssessmentConfig, listPublishedSlugs } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { rankExploreCandidates } from "@/lib/explorePersonalization";
import { getMasterProfile } from "@/lib/masterProfile";

// The deliberate full-catalog surface — everywhere else in the product stays
// focused on the single experience a user entered through or was pointed to
// (docs/ARCHITECTURE.md — Progressive Discovery / Explore Mode).
//
// Forced dynamic: this is the one catalog-reading route with a fixed path
// (every other one is under the open-ended /[slug] segment, which Next.js
// never prerenders without generateStaticParams) — without this it gets
// statically prerendered once at build time and silently stops reflecting
// newly published experiences, breaking the same "publish = live
// immediately, no deploy" guarantee every other page already has.
export const dynamic = "force-dynamic";

export default async function ExplorePage() {
  const slugs = await listPublishedSlugs();
  const configs = (await Promise.all(slugs.map((slug) => getAssessmentConfig(slug)))).filter(
    (c): c is NonNullable<typeof c> => c !== null
  );
  const configBySlug = new Map(configs.map((c) => [c.slug, c]));

  const anonymousSessionId = await readAnonymousSessionId();
  const accessUserId = await readAccessUserId();

  const [ranked, masterProfile] = anonymousSessionId
    ? await Promise.all([
        rankExploreCandidates({ anonymousSessionId, publishedSlugs: slugs }),
        getMasterProfile({ anonymousSessionId, accessUserId }),
      ])
    : [null, null];

  const orderedSlugs = ranked ? ranked.map((r) => r.slug) : slugs;
  const completedSlugs = new Set(ranked?.filter((r) => r.completed).map((r) => r.slug) ?? []);
  const recommendedSlugs = new Set(
    ranked
      ?.filter((r) => !r.completed && r.relevanceScore > 0)
      .slice(0, 2)
      .map((r) => r.slug) ?? []
  );

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Explore INNER</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Every pattern is a different door in.
      </h1>

      {masterProfile && masterProfile.insights.length > 0 && (
        <div className="mt-8 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Your signature so far</p>
          <p className="mt-2 text-[13px] text-[var(--inner-muted)]">
            Based on {masterProfile.completedAssessments.length} patterns you&apos;ve explored
          </p>
          <div className="mt-4 space-y-3">
            {masterProfile.insights.map((insight) => (
              <p key={insight.dimensionKey} className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
                {insight.summary}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 space-y-4 pb-12">
        {orderedSlugs.map((slug) => {
          const config = configBySlug.get(slug);
          if (!config) return null;
          const completed = completedSlugs.has(slug);
          const recommended = recommendedSlugs.has(slug);
          return (
            <Link
              key={config.slug}
              href={`/${config.slug}`}
              className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5"
            >
              {(completed || recommended) && (
                <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.15em] text-[var(--inner-accent)]">
                  {completed ? "Completed" : "Recommended for you"}
                </p>
              )}
              <h2 className="font-display text-[19px] text-[var(--inner-ink)]">{config.name}</h2>
              <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{config.hook}</p>
            </Link>
          );
        })}
      </div>
    </Screen>
  );
}
