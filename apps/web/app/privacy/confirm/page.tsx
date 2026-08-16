import { Screen } from "@inner/ui";
import { verifyPrivacyToken } from "@/lib/privacy";
import { PrivacyConfirmAction } from "@/components/PrivacyConfirmAction";

export default async function PrivacyConfirmPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const payload = verifyPrivacyToken(token);

  if (!payload || !token) {
    return (
      <Screen>
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Link no longer valid</h1>
        <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
          This link is invalid or has expired (links are valid for 30 minutes). Request a new one from the privacy
          page.
        </p>
      </Screen>
    );
  }

  const isDelete = payload.action === "delete";

  return (
    <Screen>
      <h1 className="font-display text-[24px] text-[var(--inner-ink)]">
        {isDelete ? "Confirm deleting your data" : "Confirm your data export"}
      </h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        {isDelete
          ? "This permanently erases your assessment answers and account. This can't be undone. Purchase records are kept in anonymized form only where required by law."
          : "This downloads a JSON file with everything INNER has on file for you: your assessment answers, results, orders, and marketing consent history."}
      </p>
      <PrivacyConfirmAction token={token} action={payload.action} />
    </Screen>
  );
}
