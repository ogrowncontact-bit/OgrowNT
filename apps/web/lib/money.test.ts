import { describe, expect, it } from "vitest";
import { formatPrice } from "./money";

describe("formatPrice", () => {
  it("formats EUR with the euro symbol", () => {
    expect(formatPrice(799, "EUR")).toBe("€7.99");
  });

  it("formats USD, GBP, and BRL with their own symbols, not a hardcoded euro sign", () => {
    expect(formatPrice(799, "USD")).toBe("US$7.99");
    expect(formatPrice(799, "GBP")).toBe("£7.99");
    expect(formatPrice(799, "BRL")).toContain("7.99");
    expect(formatPrice(799, "BRL")).not.toContain("€");
  });

  it("defaults to EUR when no currency is given, matching the pre-existing admin rollup convention", () => {
    expect(formatPrice(1000)).toBe("€10.00");
  });
});
