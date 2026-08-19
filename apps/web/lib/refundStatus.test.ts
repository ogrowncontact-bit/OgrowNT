import { describe, expect, it } from "vitest";
import { computeOrderStatusAfterRefund } from "./refundStatus";

describe("computeOrderStatusAfterRefund", () => {
  it("returns refunded when the total refunded meets the order amount", () => {
    expect(computeOrderStatusAfterRefund(799, 799)).toBe("refunded");
  });

  it("returns refunded when the total refunded exceeds the order amount (shouldn't happen, but never overstate as partial)", () => {
    expect(computeOrderStatusAfterRefund(799, 800)).toBe("refunded");
  });

  it("returns partially_refunded when less than the full amount has been refunded", () => {
    expect(computeOrderStatusAfterRefund(1299, 500)).toBe("partially_refunded");
  });

  it("returns partially_refunded for a token refund just above zero", () => {
    expect(computeOrderStatusAfterRefund(1299, 1)).toBe("partially_refunded");
  });
});
