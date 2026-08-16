import { describe, expect, it } from "vitest";
import { allAssessments } from "./index";
import { validateAssessmentConfig } from "./validate";

describe("assessment content consistency", () => {
  const slugs = new Set(allAssessments.map((a) => a.slug));

  it.each(allAssessments.map((a) => [a.slug, a] as const))("%s has no internal dangling references", (_slug, config) => {
    expect(validateAssessmentConfig(config)).toEqual([]);
  });

  it.each(allAssessments.map((a) => [a.slug, a] as const))("%s only recommends published, real assessments", (_slug, config) => {
    for (const candidate of config.recommendedNext) {
      expect(slugs.has(candidate.assessmentSlug)).toBe(true);
    }
  });

  it("has no duplicate slugs across the catalog", () => {
    const seen = allAssessments.map((a) => a.slug);
    expect(new Set(seen).size).toBe(seen.length);
  });
});
