import { prisma } from "@inner/db";

export interface ProductRow {
  id: string;
  assessmentId: string;
  assessmentName: string;
  productType: string;
  amountCents: number;
  currency: string;
  active: boolean;
}

/** Cross-assessment view — pricing itself is still edited per-assessment in AssessmentEditor's Pricing section, this just gives a single list across all 10. */
export async function listProductsForAdmin(): Promise<ProductRow[]> {
  const prices = await prisma.price.findMany({
    include: { assessment: { select: { id: true, name: true } } },
    orderBy: [{ assessment: { name: "asc" } }, { productType: "asc" }],
  });
  return prices.map((p) => ({
    id: p.id,
    assessmentId: p.assessment.id,
    assessmentName: p.assessment.name,
    productType: p.productType,
    amountCents: p.amountCents,
    currency: p.currency,
    active: p.active,
  }));
}
