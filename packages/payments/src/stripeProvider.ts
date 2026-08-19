import Stripe from "stripe";
import type {
  CheckoutSession,
  CreateCheckoutSessionParams,
  PaymentProvider,
  PaymentStatus,
  PaymentWebhookEvent,
  RefundParams,
  RefundResult,
} from "./types";

export class StripeProvider implements PaymentProvider {
  readonly name = "stripe";
  private stripe: Stripe;
  private webhookSecret: string;

  constructor(apiKey: string, webhookSecret: string) {
    this.stripe = new Stripe(apiKey);
    this.webhookSecret = webhookSecret;
  }

  async createCheckoutSession(params: CreateCheckoutSessionParams): Promise<CheckoutSession> {
    const session = await this.stripe.checkout.sessions.create({
      mode: "payment",
      customer_email: params.customerEmail,
      line_items: [
        {
          price_data: {
            currency: params.currency.toLowerCase(),
            unit_amount: params.amountCents,
            product_data: { name: params.productName },
          },
          quantity: 1,
        },
      ],
      success_url: params.successUrl,
      cancel_url: params.cancelUrl,
      metadata: { orderId: params.orderId },
    });

    if (!session.url) throw new Error("Stripe did not return a checkout URL");
    return { url: session.url, providerRef: session.id };
  }

  async parseWebhookEvent(rawBody: string, signature: string | null): Promise<PaymentWebhookEvent | null> {
    if (!signature) return null;
    const event = this.stripe.webhooks.constructEvent(rawBody, signature, this.webhookSecret);
    const session = event.data.object as Stripe.Checkout.Session;

    if (event.type === "checkout.session.completed") return { type: "payment_completed", providerRef: session.id };
    // Fired ~24h after an unpaid session's default expiry — the real, provider-confirmed signal for an abandoned checkout.
    if (event.type === "checkout.session.expired") return { type: "payment_cancelled", providerRef: session.id };
    return null;
  }

  async refund(params: RefundParams): Promise<RefundResult> {
    try {
      const session = await this.stripe.checkout.sessions.retrieve(params.providerRef);
      const paymentIntentId = typeof session.payment_intent === "string" ? session.payment_intent : session.payment_intent?.id;
      if (!paymentIntentId) return { ok: false, reason: "Checkout session has no associated payment" };

      const refund = await this.stripe.refunds.create({
        payment_intent: paymentIntentId,
        amount: params.amountCents,
        reason: "requested_by_customer",
      });
      return { ok: true, providerRef: refund.id };
    } catch (error) {
      return { ok: false, reason: error instanceof Error ? error.message : "Unknown refund error" };
    }
  }

  async getPaymentStatus(providerRef: string): Promise<PaymentStatus> {
    try {
      const session = await this.stripe.checkout.sessions.retrieve(providerRef);
      if (session.payment_status === "paid") return "paid";
      if (session.status === "expired") return "cancelled";
      return "pending";
    } catch {
      return "unknown";
    }
  }
}
