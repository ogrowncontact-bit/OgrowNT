import Link from "next/link";
import { Screen } from "@inner/ui";

// INNER is entered through specific experiences (/love, /intimacy, ...), not
// a homepage catalog (docs/ARCHITECTURE.md — Progressive Discovery). This
// root route is a placeholder until a marketing site exists.
export default function Home() {
  return (
    <Screen>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">INNER</p>
      <h1 className="font-display text-4xl leading-tight text-[var(--inner-ink)]">Discover what makes you, you.</h1>
      <p className="mt-4 text-[17px] leading-relaxed text-[var(--inner-ink-soft)]">
        INNER experiences are entered individually — start with one, or see everything we&apos;ve built.
      </p>
      <Link
        href="/love"
        className="mt-8 block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
      >
        How Do You Love? →
      </Link>
      <Link
        href="/explore"
        className="mt-3 block text-center text-[14px] text-[var(--inner-muted)] underline underline-offset-4"
      >
        Explore all experiences
      </Link>
    </Screen>
  );
}
