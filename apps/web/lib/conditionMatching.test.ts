import { describe, expect, it } from "vitest";
import { matchesCondition } from "./conditionMatching";

describe("matchesCondition", () => {
  it("matches when every ranged dimension falls within its bounds", () => {
    const ok = matchesCondition({ dimensionRanges: { connection: [55, 100], independence: [55, 100] } }, { connection: 80, independence: 60 });
    expect(ok).toBe(true);
  });

  it("fails when any one ranged dimension falls outside its bounds", () => {
    const ok = matchesCondition({ dimensionRanges: { connection: [55, 100], independence: [55, 100] } }, { connection: 80, independence: 10 });
    expect(ok).toBe(false);
  });

  it("treats a missing score for a ranged dimension as neutral (50)", () => {
    const ok = matchesCondition({ dimensionRanges: { security: [40, 60] } }, {});
    expect(ok).toBe(true);
  });

  it("ignores a dimension entry with no range at all", () => {
    const ok = matchesCondition({ dimensionRanges: { security: undefined } }, { security: 0 });
    expect(ok).toBe(true);
  });

  it("matches an empty condition unconditionally", () => {
    expect(matchesCondition({ dimensionRanges: {} }, { anything: 1 })).toBe(true);
  });
});
