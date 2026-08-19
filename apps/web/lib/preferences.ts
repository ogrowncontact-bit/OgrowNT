import { prisma } from "@inner/db";

const CONSENT_VERSION = "v1"; // matches CheckoutForm.tsx's checkout-time consent version

export interface MarketingPreference {
  subscribed: boolean;
}

/** The two tables that jointly gate a marketing send (see lib/reengagement.ts) reduced to one boolean the UI can show and toggle. */
export async function getMarketingPreference(userId: string): Promise<MarketingPreference> {
  const [latestConsent, unsubscribed] = await Promise.all([
    prisma.marketingConsent.findFirst({ where: { userId }, orderBy: { consentTimestamp: "desc" } }),
    prisma.unsubscribe.findUnique({ where: { userId_scope: { userId, scope: "all" } } }),
  ]);
  return { subscribed: (latestConsent?.consent ?? false) && !unsubscribed };
}

/**
 * Records a new consent event (append-only history, never overwritten —
 * same pattern as checkout's marketing consent capture) and keeps the
 * Unsubscribe table in sync, since that's the table lib/reengagement.ts
 * actually checks before sending. Never touches report access.
 */
export async function setMarketingPreference(userId: string, subscribed: boolean): Promise<void> {
  await prisma.marketingConsent.create({
    data: { userId, consent: subscribed, consentVersion: CONSENT_VERSION, consentSource: "preferences" },
  });

  if (subscribed) {
    await prisma.unsubscribe.deleteMany({ where: { userId, scope: "all" } });
  } else {
    await prisma.unsubscribe.upsert({
      where: { userId_scope: { userId, scope: "all" } },
      update: {},
      create: { userId, scope: "all" },
    });
  }
}
