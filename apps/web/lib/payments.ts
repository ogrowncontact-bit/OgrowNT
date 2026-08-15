import { MockProvider, StripeProvider, type PaymentProvider } from "@inner/payments";

let provider: PaymentProvider | undefined;

/**
 * Stripe when configured; otherwise a dev-only mock that routes "checkout"
 * back into our own app (see /checkout/mock). Refuses to fall back to the
 * mock in production — a missing key there should fail loudly, not
 * silently start granting free purchases.
 */
export function getPaymentProvider(): PaymentProvider {
  if (provider) return provider;

  const stripeKey = process.env.STRIPE_SECRET_KEY;
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

  if (stripeKey && webhookSecret) {
    provider = new StripeProvider(stripeKey, webhookSecret);
    return provider;
  }

  if (process.env.NODE_ENV === "production") {
    throw new Error("STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET are required in production");
  }

  console.warn("[payments] No Stripe keys configured — using MockProvider (dev only).");
  provider = new MockProvider(process.env.APP_BASE_URL ?? "http://localhost:3000");
  return provider;
}

export function isMockPayments(): boolean {
  return getPaymentProvider().name === "mock";
}
