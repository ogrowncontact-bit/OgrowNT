import { prisma } from "@inner/db";

export interface AdminOrderRow {
  id: string;
  createdAt: Date;
  paidAt: Date | null;
  email: string;
  assessmentName: string;
  productType: string;
  amountCents: number;
  currency: string;
  status: string;
  provider: string;
  refundedCents: number;
  reportStatus: string | null;
}

/** Newest first — the canonical per-purchase view, per docs/ARCHITECTURE.md §10 admin conventions. */
export async function listOrdersForAdmin(limit = 100): Promise<AdminOrderRow[]> {
  const orders = await prisma.order.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: { user: true, price: { include: { assessment: true } }, refunds: true, reports: true },
  });

  return orders.map((o) => ({
    id: o.id,
    createdAt: o.createdAt,
    paidAt: o.paidAt,
    email: o.user.email,
    assessmentName: o.price.assessment.name,
    productType: o.price.productType,
    amountCents: o.amountCents,
    currency: o.currency,
    status: o.status,
    provider: o.provider,
    refundedCents: o.refunds.reduce((sum, r) => sum + r.amountCents, 0),
    reportStatus: o.reports[0]?.status ?? null,
  }));
}
