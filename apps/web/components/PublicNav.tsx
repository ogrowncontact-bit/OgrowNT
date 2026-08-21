import Link from "next/link";

/**
 * The one shared nav element for browsing pages (home, explore, landing
 * pages) — deliberately excluded from assessment-taking session subroutes
 * to preserve the "one primary action, no distraction" flow (see Screen's
 * own doc comment in packages/ui).
 */
export function PublicNav() {
  return (
    <nav className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <Link href="/" className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        INNER
      </Link>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-x-4">
        <Link href="/explore" className="text-xs font-medium text-[var(--inner-muted)] underline underline-offset-4">
          Explore
        </Link>
        <Link href="/how-it-works" className="text-xs font-medium text-[var(--inner-muted)] underline underline-offset-4">
          How it works
        </Link>
        <Link href="/my-discoveries" className="text-xs font-medium text-[var(--inner-muted)] underline underline-offset-4">
          My Discoveries
        </Link>
        <Link href="/about" className="text-xs font-medium text-[var(--inner-muted)] underline underline-offset-4">
          About
        </Link>
        <Link href="/privacy-policy" className="text-xs text-[var(--inner-muted)] underline underline-offset-4 opacity-70">
          Privacy
        </Link>
      </div>
    </nav>
  );
}
