import { prisma } from "@inner/db";
import { renderRefundConfirmationEmail } from "@inner/email";
import { getPaymentProvider } from "@/lib/payments";
import { computeOrderStatusAfterRefund } from "@/lib/refundStatus";
import { getEmailProvider } from "@/lib/email";
import { recordEmailEvent } from "@/lib/emailEvents";
import { formatPrice } from "@/lib/money";

/**
 * Issues a real refund through the configured PaymentProvider, then records
 * it. Deliberately does not revoke the buyer's existing report access
 * (Entitlement) — they already received what they paid for; a refund
 * reverses the charge, not the delivery, unless a human decides otherwise
 * through some other, explicit action.
 *
 * amountCents is optional and defaults to a full refund of whatever hasn't
 * already been refunded — pass a smaller amount for a partial refund. The
 * order moves to "refunded" once the sum of all refunds reaches the
 * original charge, "partially_refunded" otherwise, and stays refundable
 * (an already-partially-refunded order can be refunded again) until then.
 */
export async function issueRefund(
  orderId: string,
  reason?: string,
  amountCents?: number
): Promise<{ ok: true } | { ok: false; error: string }> {
  const order = await prisma.order.findUnique({
    where: { id: orderId },
    include: { refunds: true, user: true, price: { include: { assessment: true } } },
  });
  if (!order) return { ok: false, error: "Order not found" };
  if (order.status !== "paid" && order.status !== "partially_refunded") {
    return { ok: false, error: `Order status is "${order.status}" — nothing left to refund` };
  }
  if (!order.providerRef) return { ok: false, error: "Order has no payment reference on file" };

  const alreadyRefundedCents = order.refunds.reduce((sum, r) => sum + r.amountCents, 0);
  const remainingCents = order.amountCents - alreadyRefundedCents;
  const refundCents = amountCents ?? remainingCents;
  if (refundCents <= 0) return { ok: false, error: "Nothing left to refund on this order" };
  if (refundCents > remainingCents) {
    return { ok: false, error: `Only ${remainingCents} cents remain refundable on this order` };
  }

  const result = await getPaymentProvider().refund({
    providerRef: order.providerRef,
    amountCents: refundCents,
    reason,
  });
  if (!result.ok) return { ok: false, error: result.reason ?? "Refund failed" };

  const newStatus = computeOrderStatusAfterRefund(order.amountCents, alreadyRefundedCents + refundCents);
  await prisma.$transaction([
    prisma.refund.create({ data: { orderId, amountCents: refundCents, reason } }),
    prisma.order.update({ where: { id: orderId }, data: { status: newStatus } }),
  ]);

  const sendResult = await getEmailProvider().send({
    to: order.user.email,
    subject: `${order.price.assessment.name} — refund confirmation`,
    html: renderRefundConfirmationEmail({
      assessmentName: order.price.assessment.name,
      refundAmountLabel: formatPrice(refundCents, order.currency),
      partial: newStatus === "partially_refunded",
    }),
  });
  await recordEmailEvent({
    userId: order.userId,
    type: "refund_confirmation",
    templateKey: "refund_confirmation_v1",
    providerRef: sendResult.providerRef,
    relatedEntityId: order.id,
    status: sendResult.ok ? "sent" : "failed",
  });

  return { ok: true };
}
