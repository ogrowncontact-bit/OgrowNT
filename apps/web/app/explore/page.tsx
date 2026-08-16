import Link from "next/link";
import { Screen } from "@inner/ui";
import { getAssessmentConfig, listPublishedSlugs } from "@/lib/assessments";

// The deliberate full-catalog surface — everywhere else in the product stays
// focused on the single experience a user entered through or was pointed to
// (docs/ARCHITECTURE.md — Progressive Discovery / Explore Mode).
export default function ExplorePage() {
  const configs = listPublishedSlugs()
    .map((slug) => getAssessmentConfig(slug))
    .filter((c): c is NonNullable<typeof c> => c !== null);

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Explore INNER</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Every pattern is a different door in.
      </h1>

      <div className="mt-8 space-y-4 pb-12">
        {configs.map((config) => (
          <Link
            key={config.slug}
            href={`/${config.slug}`}
            className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5"
          >
            <h2 className="font-display text-[19px] text-[var(--inner-ink)]">{config.name}</h2>
            <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{config.hook}</p>
          </Link>
        ))}
      </div>
    </Screen>
  );
}
