/** Pure order-status computation after a refund — kept DB-free so it's directly testable (see docs on the conditionMatching.ts/exploreRanking.ts split elsewhere in this package). */
export function computeOrderStatusAfterRefund(orderAmountCents: number, totalRefundedCents: number): "refunded" | "partially_refunded" {
  return totalRefundedCents >= orderAmountCents ? "refunded" : "partially_refunded";
}
