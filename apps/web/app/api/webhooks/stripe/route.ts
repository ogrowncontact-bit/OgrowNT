import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { getPaymentProvider } from "@/lib/payments";
import { completeOrder } from "@/lib/commerce";
import { track } from "@/lib/analytics";

/** Real Stripe webhook — the only trigger that grants an entitlement in production. Unreachable/no-op path while MockProvider is active. */
export async function POST(request: NextRequest) {
  const rawBody = await request.text();
  const signature = request.headers.get("stripe-signature");

  let event;
  try {
    event = await getPaymentProvider().parseWebhookEvent(rawBody, signature);
  } catch (error) {
    console.error("[webhooks/stripe] signature verification failed", error);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  if (!event) return NextResponse.json({ ok: true }); // event we don't act on

  const order = await prisma.order.findFirst({ where: { providerRef: event.providerRef }, include: { assessmentSession: true } });
  if (!order) {
    console.error(`[webhooks/stripe] no order found for providerRef ${event.providerRef}`);
    return NextResponse.json({ error: "Order not found" }, { status: 404 });
  }

  if (event.type === "payment_completed") {
    await completeOrder(order.id);
    return NextResponse.json({ ok: true });
  }

  // payment_cancelled (checkout.session.expired) — only meaningful for an
  // order that's still pending; a session can outlive an order that was
  // already completed or cancelled by an earlier delivery of this same event.
  if (order.status === "pending") {
    await prisma.order.update({ where: { id: order.id }, data: { status: "cancelled" } });
    await track({
      anonymousSessionId: order.assessmentSession.anonymousSessionId,
      eventName: "checkout_abandoned",
      assessmentId: order.assessmentSession.assessmentId,
      properties: { orderId: order.id, priceId: order.priceId, currency: order.currency, amountCents: order.amountCents },
    });
  }
  return NextResponse.json({ ok: true });
}
