import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { getPaymentProvider } from "@/lib/payments";
import { completeOrder } from "@/lib/commerce";
import { markOrderCancelled } from "@/lib/orderCancellation";

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

  const order = await prisma.order.findFirst({ where: { providerRef: event.providerRef } });
  if (!order) {
    console.error(`[webhooks/stripe] no order found for providerRef ${event.providerRef}`);
    return NextResponse.json({ error: "Order not found" }, { status: 404 });
  }

  if (event.type === "payment_completed") {
    await completeOrder(order.id);
  } else {
    // payment_cancelled (checkout.session.expired) — markOrderCancelled is a
    // no-op if the order already moved past "pending" (completed by a
    // webhook that arrived first, or already cancelled by an earlier
    // delivery of this same event).
    await markOrderCancelled(order.id);
  }
  return NextResponse.json({ ok: true });
}
