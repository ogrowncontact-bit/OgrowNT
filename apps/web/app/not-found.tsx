import Link from "next/link";
import { Screen } from "@inner/ui";

export default function NotFound() {
  return (
    <Screen
      footer={
        <Link
          href="/explore"
          className="block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
        >
          Explore all experiences
        </Link>
      }
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">INNER</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Looks like this discovery doesn&apos;t exist yet.
      </h1>
      <p className="mt-4 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        The page you&apos;re looking for may have moved or never existed. Here&apos;s everything we&apos;ve built
        so far.
      </p>
    </Screen>
  );
}
