import { describe, expect, it } from "vitest";
import { bucketConfidence } from "./confidence";

describe("bucketConfidence", () => {
  it("buckets high confidence", () => {
    expect(bucketConfidence(1)).toBe("high");
    expect(bucketConfidence(0.66)).toBe("high");
  });

  it("buckets medium confidence", () => {
    expect(bucketConfidence(0.5)).toBe("medium");
    expect(bucketConfidence(0.33)).toBe("medium");
  });

  it("buckets low confidence", () => {
    expect(bucketConfidence(0.32)).toBe("low");
    expect(bucketConfidence(0)).toBe("low");
  });
});
