/**
 * Payment provider abstraction — docs/ARCHITECTURE.md §1.1: "Payment
 * provider should be abstracted so it can be replaced if necessary."
 * Nothing outside this package (and its selected implementation) should
 * import the Stripe SDK directly.
 */
export interface CreateCheckoutSessionParams {
  orderId: string;
  amountCents: number;
  currency: string;
  productName: string;
  customerEmail: string;
  successUrl: string;
  cancelUrl: string;
}

export interface CheckoutSession {
  url: string;
  providerRef: string;
}

export interface PaymentCompletedEvent {
  type: "payment_completed";
  providerRef: string; // the checkout session id the provider gave us
}

export interface PaymentProvider {
  readonly name: string;
  createCheckoutSession(params: CreateCheckoutSessionParams): Promise<CheckoutSession>;
  /** Verifies and parses a webhook payload. Returns null for events we don't act on. */
  parseWebhookEvent(rawBody: string, signature: string | null): Promise<PaymentCompletedEvent | null>;
}
