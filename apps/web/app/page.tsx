import Link from "next/link";
import { Screen } from "@inner/ui";
import { getAssessmentConfig, listPublishedSlugs } from "@/lib/assessments";
import { TRUST_POINTS } from "@/lib/landingContent";
import { PublicNav } from "@/components/PublicNav";

const HOW_IT_WORKS = [
  "Pick an experience that matches how you want to understand yourself",
  "Answer a short, adaptive set of questions — no two people see the same path",
  "See your personalized result immediately",
  "Unlock the complete report if you want to go deeper",
];

// The deliberate full-catalog surface stays at /explore
// (docs/ARCHITECTURE.md — Progressive Discovery / Explore Mode); this
// homepage introduces the platform and surfaces the live catalog directly,
// without singling out any one experience as "the" flagship.
//
// Forced dynamic for the same reason /explore is: a fixed-path route that
// reads the catalog needs to reflect newly published experiences
// immediately, not just at the next build.
export const dynamic = "force-dynamic";

export default async function Home() {
  const slugs = await listPublishedSlugs();
  const configs = (await Promise.all(slugs.map((slug) => getAssessmentConfig(slug)))).filter(
    (c): c is NonNullable<typeof c> => c !== null
  );
  configs.sort((a, b) => a.name.localeCompare(b.name));

  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <h1 className="font-display text-[34px] leading-[1.15] text-[var(--inner-ink)]">
        Discover what makes you, you.
      </h1>
      <p className="mt-5 text-[18px] leading-relaxed text-[var(--inner-ink-soft)]">
        Short, adaptive conversations that reveal real patterns in how you love, decide, connect, and show up —
        no account needed, results in minutes.
      </p>
      <Link
        href="/explore"
        className="mt-8 block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
      >
        Explore all experiences →
      </Link>

      {configs.length > 0 && (
        <section className="mt-14">
          <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">
            Choose where to start
          </h2>
          <div className="mt-4 space-y-4">
            {configs.map((config) => (
              <Link
                key={config.slug}
                href={`/${config.slug}`}
                className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5"
              >
                <h3 className="font-display text-[19px] text-[var(--inner-ink)]">{config.name}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{config.hook}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="mt-14">
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

      <section className="mb-8 mt-14">
        <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">Privacy</h2>
        <ul className="mt-4 space-y-2">
          {TRUST_POINTS.map((point) => (
            <li key={point} className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
              {point}
            </li>
          ))}
        </ul>
      </section>
    </Screen>
  );
}
