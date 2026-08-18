import { Screen } from "@inner/ui";
import { verifyAccessLinkToken } from "@/lib/access";
import { AccessConfirmAction } from "@/components/AccessConfirmAction";

export const metadata = { robots: { index: false, follow: false } };

export default async function AccessConfirmPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const payload = verifyAccessLinkToken(token);

  if (!payload || !token) {
    return (
      <Screen>
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Link no longer valid</h1>
        <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
          This link is invalid or has expired (links are valid for 30 minutes). Request a new one from the access
          page.
        </p>
      </Screen>
    );
  }

  return (
    <Screen>
      <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Access your reports</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        Confirm below to view every INNER report purchased with this email, on this device.
      </p>
      <AccessConfirmAction token={token} />
    </Screen>
  );
}
