import { describe, expect, it } from "vitest";
import { aggregateDimension, buildInsights, type MasterProfileDimensionReading } from "./masterProfileInsights";

function reading(overrides: Partial<MasterProfileDimensionReading>): MasterProfileDimensionReading {
  return { slug: "love", assessmentName: "How Do You Love?", score: 50, confidence: 1, ...overrides };
}

describe("aggregateDimension", () => {
  it("weights the average by confidence when confidence signal exists", () => {
    const result = aggregateDimension("trust", "Trust", [
      reading({ slug: "love", score: 80, confidence: 1 }),
      reading({ slug: "jealousy", score: 40, confidence: 0 }),
    ]);
    // confidence-0 reading should be excluded from the weighted average, not just discounted
    expect(result.averageScore).toBe(80);
  });

  it("falls back to a plain average when every reading has zero confidence", () => {
    const result = aggregateDimension("trust", "Trust", [
      reading({ slug: "love", score: 80, confidence: 0 }),
      reading({ slug: "jealousy", score: 40, confidence: 0 }),
    ]);
    expect(result.averageScore).toBe(60);
  });

  it("flags divergent when readings spread past the threshold", () => {
    const result = aggregateDimension("security", "Security", [
      reading({ slug: "love", score: 67, confidence: 1 }),
      reading({ slug: "jealousy", score: 39, confidence: 1 }),
    ]);
    expect(result.divergent).toBe(true);
  });

  it("does not flag divergent for readings that cluster together", () => {
    const result = aggregateDimension("trust", "Trust", [
      reading({ slug: "love", score: 70, confidence: 1 }),
      reading({ slug: "jealousy", score: 75, confidence: 1 }),
    ]);
    expect(result.divergent).toBe(false);
  });
});

describe("buildInsights", () => {
  it("surfaces a divergent_pattern insight for the highest-average divergent dimension", () => {
    const insights = buildInsights([
      aggregateDimension("validation", "Validation", [
        reading({ slug: "love", score: 75, confidence: 1 }),
        reading({ slug: "jealousy", score: 33, confidence: 1 }),
      ]),
    ]);
    expect(insights[0].kind).toBe("divergent_pattern");
    expect(insights[0].summary).toContain("33");
    expect(insights[0].summary).toContain("75");
  });

  it("surfaces a consistent_strength insight for a non-divergent high-scoring dimension", () => {
    const insights = buildInsights([
      aggregateDimension("trust", "Trust", [
        reading({ slug: "love", score: 80, confidence: 1 }),
        reading({ slug: "jealousy", score: 75, confidence: 1 }),
      ]),
    ]);
    expect(insights.some((i) => i.kind === "consistent_strength" && i.dimensionKey === "trust")).toBe(true);
  });

  it("surfaces a consistent_friction insight for a non-divergent low-scoring dimension", () => {
    const insights = buildInsights([
      aggregateDimension("vulnerability", "Vulnerability", [
        reading({ slug: "love", score: 20, confidence: 1 }),
        reading({ slug: "jealousy", score: 25, confidence: 1 }),
      ]),
    ]);
    expect(insights.some((i) => i.kind === "consistent_friction" && i.dimensionKey === "vulnerability")).toBe(true);
  });

  it("never lists a divergent dimension as a consistent strength or friction", () => {
    const insights = buildInsights([
      aggregateDimension("control", "Control", [
        reading({ slug: "love", score: 90, confidence: 1 }),
        reading({ slug: "jealousy", score: 10, confidence: 1 }),
      ]),
    ]);
    expect(insights.filter((i) => i.dimensionKey === "control" && i.kind !== "divergent_pattern")).toHaveLength(0);
  });

  it("caps the result at 3 insights", () => {
    const dims = [
      aggregateDimension("a", "A", [reading({ score: 90 }), reading({ score: 10 })]), // divergent
      aggregateDimension("b", "B", [reading({ score: 80 }), reading({ score: 75 })]), // strength
      aggregateDimension("c", "C", [reading({ score: 20 }), reading({ score: 15 })]), // friction
      aggregateDimension("d", "D", [reading({ score: 85 }), reading({ score: 82 })]), // another strength, should be dropped
    ];
    expect(buildInsights(dims)).toHaveLength(3);
  });

  it("returns no insights when there is nothing worth saying", () => {
    const insights = buildInsights([
      aggregateDimension("communication", "Communication", [reading({ score: 50 }), reading({ score: 52 })]),
    ]);
    expect(insights).toHaveLength(0);
  });
});
