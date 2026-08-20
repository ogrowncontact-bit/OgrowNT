import type { Metadata } from "next";
import Link from "next/link";
import { Screen } from "@inner/ui";
import { PublicNav } from "@/components/PublicNav";
import { TRUST_POINTS } from "@/lib/landingContent";
import { getSiteUrl } from "@/lib/siteUrl";

const title = "How INNER Works";
const description = "A short, adaptive conversation that reveals a real pattern — no account, no diagnosis, just a personal discovery.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${getSiteUrl()}/how-it-works` },
  openGraph: { title, description, url: `${getSiteUrl()}/how-it-works`, type: "website" },
  twitter: { card: "summary_large_image", title, description },
};

const STEPS = [
  { title: "Answer thoughtful questions", body: "A short, adaptive set of questions — the next one adapts to what you've already told us, so no two people see the same path." },
  { title: "INNER identifies meaningful patterns", body: "Your answers are scored across real dimensions, and any tension or contradiction in how you answered is noticed, not ignored." },
  { title: "Receive your personalized free insight", body: "As soon as you finish, you see a free result — your primary pattern, described honestly, no sign-up required." },
  { title: "Unlock your complete report if you wish", body: "If you want to go deeper, a full personalized report is available — your dimensions, strengths, tensions, and reflection questions, in one place." },
];

export default function HowItWorksPage() {
  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">How it works</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Four steps. No account. A few minutes.
      </h1>

      <ol className="mt-10 space-y-8">
        {STEPS.map((step, i) => (
          <li key={step.title} className="flex gap-4">
            <span
              aria-hidden
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--inner-card)] font-display text-[14px] text-[var(--inner-ink)]"
            >
              {i + 1}
            </span>
            <div>
              <h2 className="font-display text-[17px] text-[var(--inner-ink)]">{step.title}</h2>
              <p className="mt-1 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

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

      <Link
        href="/explore"
        className="mb-16 block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
      >
        Explore Your First Discovery
      </Link>
    </Screen>
  );
}
