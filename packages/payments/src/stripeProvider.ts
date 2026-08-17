import Stripe from "stripe";
import type { CheckoutSession, CreateCheckoutSessionParams, PaymentCompletedEvent, PaymentProvider, RefundParams, RefundResult } from "./types";

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

  async parseWebhookEvent(rawBody: string, signature: string | null): Promise<PaymentCompletedEvent | null> {
    if (!signature) return null;
    const event = this.stripe.webhooks.constructEvent(rawBody, signature, this.webhookSecret);
    if (event.type !== "checkout.session.completed") return null;
    const session = event.data.object as Stripe.Checkout.Session;
    return { type: "payment_completed", providerRef: session.id };
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
}
