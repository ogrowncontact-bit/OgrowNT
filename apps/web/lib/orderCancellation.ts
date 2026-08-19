import { prisma } from "@inner/db";
import { renderPaymentFailedEmail } from "@inner/email";
import { getEmailProvider } from "./email";
import { track } from "./analytics";
import { recordEmailEvent } from "./emailEvents";

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/**
 * Shared by the Stripe webhook's payment_cancelled branch and the admin
 * manual-reconciliation path (lib/admin/orderReconciliation.ts) — both
 * learn about a checkout expiring unpaid the same way and need to do the
 * same three things: mark it, track it, and let the customer know. A
 * no-op if the order has already moved past "pending" (completed by a
 * webhook that arrived first, or already marked cancelled by an earlier
 * delivery of the same event).
 */
export async function markOrderCancelled(orderId: string): Promise<void> {
  const order = await prisma.order.findUnique({
    where: { id: orderId },
    include: { assessmentSession: true, user: true, price: { include: { assessment: true } } },
  });
  if (!order || order.status !== "pending") return;

  await prisma.order.update({ where: { id: order.id }, data: { status: "cancelled" } });
  await track({
    anonymousSessionId: order.assessmentSession.anonymousSessionId,
    eventName: "checkout_abandoned",
    assessmentId: order.assessmentSession.assessmentId,
    properties: { orderId: order.id, priceId: order.priceId, currency: order.currency, amountCents: order.amountCents },
  });

  const retryUrl = `${appBaseUrl()}/${order.assessmentSession.sourceSlug}/session/${order.assessmentSessionId}/checkout`;
  const sendResult = await getEmailProvider().send({
    to: order.user.email,
    subject: `${order.price.assessment.name} — your payment wasn't completed`,
    html: renderPaymentFailedEmail({ assessmentName: order.price.assessment.name, retryUrl }),
  });
  await recordEmailEvent({
    userId: order.userId,
    type: "payment_failed",
    templateKey: "payment_failed_v1",
    providerRef: sendResult.providerRef,
    relatedEntityId: order.id,
    status: sendResult.ok ? "sent" : "failed",
  });
}
