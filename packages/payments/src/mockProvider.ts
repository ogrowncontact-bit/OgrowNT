import type { CheckoutSession, CreateCheckoutSessionParams, PaymentCompletedEvent, PaymentProvider, RefundParams, RefundResult } from "./types";

/**
 * Dev-only stand-in for local testing without real Stripe keys. Points the
 * "checkout" at our own app instead of Stripe — the caller (apps/web) is
 * responsible for refusing to construct this in production (see
 * getPaymentProvider in apps/web/lib/payments.ts).
 */
export class MockProvider implements PaymentProvider {
  readonly name = "mock";
  constructor(private appBaseUrl: string) {}

  async createCheckoutSession(params: CreateCheckoutSessionParams): Promise<CheckoutSession> {
    return {
      url: `${this.appBaseUrl}/checkout/mock/${params.orderId}`,
      providerRef: `mock_${params.orderId}`,
    };
  }

  async parseWebhookEvent(): Promise<PaymentCompletedEvent | null> {
    // The mock flow completes orders via a direct app route, not a webhook.
    return null;
  }

  async refund(params: RefundParams): Promise<RefundResult> {
    return { ok: true, providerRef: `mock_refund_${params.providerRef}` };
  }
}
