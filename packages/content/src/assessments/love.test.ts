import { describe, expect, it } from "vitest";
import { loveAssessment } from "./love";

// LOVE is the reference implementation every other experience's config
// should follow — these assertions exist to catch a future edit that
// quietly regresses it back toward a prototype-sized question bank or
// profile taxonomy, not to re-validate structural correctness (validate.test.ts
// already does that for every assessment, including this one).
describe("LOVE — reference implementation shape", () => {
  it("has at least 40 candidate questions across core + adaptive pool", () => {
    const total = loveAssessment.questionBank.core.length + loveAssessment.questionBank.adaptivePool.length;
    expect(total).toBeGreaterThanOrEqual(40);
  });

  it("has exactly 10 dimensions", () => {
    expect(loveAssessment.dimensions).toHaveLength(10);
  });

  it("has exactly 8 named profiles", () => {
    expect(loveAssessment.profiles).toHaveLength(8);
    const expectedNames = [
      "The Independent Connector",
      "The Deep Connector",
      "The Selective Heart",
      "The Secure Explorer",
      "The Careful Observer",
      "The Reassurance Seeker",
      "The Self-Protector",
      "The Balanced Connector",
    ];
    expect(loveAssessment.profiles.map((p) => p.name).sort()).toEqual(expectedNames.sort());
  });

  it("a normal session falls within 12-18 questions, and 18 is a ceiling, not a target", () => {
    expect(loveAssessment.minQuestions).toBe(12);
    expect(loveAssessment.recommendedQuestions).toBeLessThan(loveAssessment.maxQuestions);
    expect(loveAssessment.maxQuestions).toBe(18);
  });

  it("uses at most 3 open_text questions across the whole bank", () => {
    const allQuestions = [...loveAssessment.questionBank.core, ...loveAssessment.questionBank.adaptivePool];
    const openCount = allQuestions.filter((q) => q.type === "open_text").length;
    expect(openCount).toBeGreaterThan(0);
    expect(openCount).toBeLessThanOrEqual(3);
  });

  it("single_select is the dominant question type, not open_text or scale", () => {
    const allQuestions = [...loveAssessment.questionBank.core, ...loveAssessment.questionBank.adaptivePool];
    const singleSelectCount = allQuestions.filter((q) => q.type === "single_select").length;
    expect(singleSelectCount).toBeGreaterThan(allQuestions.length / 2);
  });

  it("declares at least 3 tension pairs among its dimensions", () => {
    expect(loveAssessment.tensionPairs?.length ?? 0).toBeGreaterThanOrEqual(3);
    for (const pair of loveAssessment.tensionPairs ?? []) {
      const dimKeys = new Set(loveAssessment.dimensions.map((d) => d.key));
      expect(dimKeys.has(pair.dimensionA)).toBe(true);
      expect(dimKeys.has(pair.dimensionB)).toBe(true);
    }
  });

  it("has a share template that references the resolved profile name, not raw answers", () => {
    expect(loveAssessment.shareTemplate?.shareTextTemplate).toContain("{{profileName}}");
    expect(loveAssessment.shareTemplate?.shareTextTemplate).not.toMatch(/score|answer|dimension/i);
  });

  it("every profile with optional/exclude conditions only references declared dimensions", () => {
    const dimKeys = new Set(loveAssessment.dimensions.map((d) => d.key));
    for (const profile of loveAssessment.profiles) {
      for (const dimKey of Object.keys(profile.matchingRule.optionalConditions ?? {})) {
        expect(dimKeys.has(dimKey)).toBe(true);
      }
      for (const dimKey of Object.keys(profile.matchingRule.excludeConditions ?? {})) {
        expect(dimKeys.has(dimKey)).toBe(true);
      }
    }
  });
});
