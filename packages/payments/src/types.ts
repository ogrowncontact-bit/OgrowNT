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

/** Fired when a checkout session expires unpaid — the real, provider-confirmed signal for an abandoned checkout, as opposed to a guess based on elapsed time. */
export interface PaymentCancelledEvent {
  type: "payment_cancelled";
  providerRef: string;
}

export type PaymentWebhookEvent = PaymentCompletedEvent | PaymentCancelledEvent;

export type PaymentStatus = "pending" | "paid" | "cancelled" | "unknown";

export interface RefundParams {
  /** The checkout session id from CheckoutSession.providerRef — providers that need the underlying charge/payment-intent id look it up from this. */
  providerRef: string;
  amountCents: number;
  reason?: string;
}

export interface RefundResult {
  ok: boolean;
  providerRef?: string;
  reason?: string;
}

export interface PaymentProvider {
  readonly name: string;
  createCheckoutSession(params: CreateCheckoutSessionParams): Promise<CheckoutSession>;
  /** Verifies and parses a webhook payload. Returns null for events we don't act on. */
  parseWebhookEvent(rawBody: string, signature: string | null): Promise<PaymentWebhookEvent | null>;
  refund(params: RefundParams): Promise<RefundResult>;
  /** Manual reconciliation for a stuck order — e.g. an admin checking a "pending" order whose webhook may have been missed. Never the primary confirmation path; the webhook is. */
  getPaymentStatus(providerRef: string): Promise<PaymentStatus>;
}
