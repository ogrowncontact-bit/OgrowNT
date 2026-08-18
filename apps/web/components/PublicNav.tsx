import Link from "next/link";

/**
 * The one shared nav element for browsing pages (home, explore, landing
 * pages) — deliberately excluded from assessment-taking session subroutes
 * to preserve the "one primary action, no distraction" flow (see Screen's
 * own doc comment in packages/ui).
 */
export function PublicNav() {
  return (
    <nav className="flex items-center justify-between">
      <Link href="/" className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        INNER
      </Link>
      <Link href="/explore" className="text-xs font-medium text-[var(--inner-muted)] underline underline-offset-4">
        Explore
      </Link>
    </nav>
  );
}
