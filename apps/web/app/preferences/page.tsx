import Link from "next/link";
import { redirect } from "next/navigation";
import { Screen } from "@inner/ui";
import { readAccessUserId } from "@/lib/access";
import { getMarketingPreference } from "@/lib/preferences";
import { PreferenceToggle } from "@/components/PreferenceToggle";

export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false, follow: false } };

export default async function PreferencesPage() {
  const userId = await readAccessUserId();
  if (!userId) redirect("/access");

  const { subscribed } = await getMarketingPreference(userId);

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Preferences</p>
      <h1 className="font-display text-[26px] leading-tight text-[var(--inner-ink)]">Email preferences</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        This only controls recommendations and updates. We&apos;ll always email you a report you&apos;ve purchased —
        that&apos;s not a marketing email, and changing this never affects your access to it.
      </p>

      <div className="mt-8">
        <PreferenceToggle initialSubscribed={subscribed} />
      </div>

      <p className="mt-10 text-[13px] text-[var(--inner-muted)]">
        <Link href="/access/reports" className="underline">
          Back to your reports
        </Link>
      </p>
    </Screen>
  );
}
