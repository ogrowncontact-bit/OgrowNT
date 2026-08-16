import { prisma } from "@inner/db";
import { Screen } from "@inner/ui";
import { verifyToken } from "@/lib/security/signedToken";

export default async function UnsubscribePage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const payload = verifyToken<{ userId: string }>(token);

  if (!payload) {
    return (
      <Screen>
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Link no longer valid</h1>
        <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
          This unsubscribe link is invalid or has expired. If you're still receiving emails you don't want, reply to
          any of them and we'll take care of it.
        </p>
      </Screen>
    );
  }

  await prisma.unsubscribe.upsert({
    where: { userId_scope: { userId: payload.userId, scope: "all" } },
    update: {},
    create: { userId: payload.userId, scope: "all" },
  });

  return (
    <Screen>
      <h1 className="font-display text-[24px] text-[var(--inner-ink)]">You're unsubscribed</h1>
      <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
        You won't receive recommendation or update emails from INNER anymore. We'll still email you a report you've
        already paid for, since that's not a marketing email.
      </p>
    </Screen>
  );
}
