import { prisma } from "@inner/db";
import { getPaymentProvider } from "@/lib/payments";
import { completeOrder } from "@/lib/commerce";
import { markOrderCancelled } from "@/lib/orderCancellation";

/**
 * Manual reconciliation for a stuck "pending" order — an admin escape hatch
 * for the rare case a webhook delivery was missed entirely (Stripe retries
 * for a while, but not forever). Never the primary confirmation path; the
 * webhook is. Queries the provider directly and, if it turns out the
 * customer did pay, runs the exact same completeOrder() the webhook would
 * have run — so the customer is never asked to pay twice just because a
 * webhook got lost.
 */
export async function checkOrderPaymentStatus(orderId: string): Promise<{ ok: true; status: string } | { ok: false; error: string }> {
  const order = await prisma.order.findUnique({ where: { id: orderId } });
  if (!order) return { ok: false, error: "Order not found" };
  if (order.status !== "pending") return { ok: false, error: `Order status is already "${order.status}"` };
  if (!order.providerRef) return { ok: false, error: "Order has no payment reference on file" };

  const status = await getPaymentProvider().getPaymentStatus(order.providerRef);

  if (status === "paid") {
    await completeOrder(order.id);
    return { ok: true, status: "paid" };
  }
  if (status === "cancelled") {
    await markOrderCancelled(order.id);
    return { ok: true, status: "cancelled" };
  }
  return { ok: true, status };
}
