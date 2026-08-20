import type { Metadata } from "next";
import Link from "next/link";
import { Screen } from "@inner/ui";
import { PublicNav } from "@/components/PublicNav";
import { getSiteUrl } from "@/lib/siteUrl";

const title = "About INNER";
const description = "INNER is a personal discovery platform — short, adaptive conversations that reveal real patterns in how you relate, decide, and connect.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${getSiteUrl()}/about` },
  openGraph: { title, description, url: `${getSiteUrl()}/about`, type: "website" },
  twitter: { card: "summary_large_image", title, description },
};

export default function AboutPage() {
  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">About</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        A personal discovery platform, not a personality quiz.
      </h1>

      <div className="mt-6 space-y-4 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        <p>
          INNER exists to help people notice patterns in themselves — how they love, decide, connect, and show up —
          without reducing them to a single label or type. Every experience is a short, adaptive conversation: the
          questions you see depend on the answers you&apos;ve already given, so no two people take the same path.
        </p>
        <p>
          We deliberately don&apos;t call this a &quot;personality test.&quot; A test implies a right answer and a
          fixed score. INNER looks for interactions — the tension between wanting closeness and needing space, for
          example — because that&apos;s closer to how people actually experience themselves than any single trait
          ever is.
        </p>
        <p>
          INNER isn&apos;t therapy, and it isn&apos;t a diagnosis. It&apos;s a starting point for reflection — free
          to try, with the option to go deeper through a personalized report if you want to.
        </p>
      </div>

      <Link
        href="/explore"
        className="mb-16 mt-10 block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
      >
        Explore Your First Discovery
      </Link>
    </Screen>
  );
}
