import { prisma } from "@inner/db";
import { getPaymentProvider } from "@/lib/payments";

/**
 * Issues a real refund through the configured PaymentProvider, then records
 * it. Deliberately does not revoke the buyer's existing report access
 * (Entitlement) — they already received what they paid for; a refund
 * reverses the charge, not the delivery, unless a human decides otherwise
 * through some other, explicit action.
 */
export async function issueRefund(orderId: string, reason?: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const order = await prisma.order.findUnique({ where: { id: orderId } });
  if (!order) return { ok: false, error: "Order not found" };
  if (order.status !== "paid") return { ok: false, error: `Order status is "${order.status}", not "paid" — nothing to refund` };
  if (!order.providerRef) return { ok: false, error: "Order has no payment reference on file" };

  const result = await getPaymentProvider().refund({
    providerRef: order.providerRef,
    amountCents: order.amountCents,
    reason,
  });
  if (!result.ok) return { ok: false, error: result.reason ?? "Refund failed" };

  await prisma.$transaction([
    prisma.refund.create({ data: { orderId, amountCents: order.amountCents, reason } }),
    prisma.order.update({ where: { id: orderId }, data: { status: "refunded" } }),
  ]);

  return { ok: true };
}
