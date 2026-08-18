import { describe, expect, it } from "vitest";
import { rankBySlugWeights, type CompletedAssessmentInput } from "./exploreRanking";

const publishedSlugs = ["love", "jealousy", "intimacy", "hidden-self", "relationship"];

describe("rankBySlugWeights", () => {
  it("returns every published slug in input order, all zero-relevance, when nothing is completed", () => {
    const result = rankBySlugWeights({ publishedSlugs, completed: [] });
    expect(result.map((r) => r.slug)).toEqual(publishedSlugs);
    expect(result.every((r) => r.relevanceScore === 0 && !r.completed)).toBe(true);
  });

  it("evaluates each completed assessment's edges against its own scores, not a scores object merged across assessments", () => {
    // Regression test for a real bug: merging every completed session's
    // dimension scores into one shared object let a later assessment's
    // reading of "security" silently overwrite an earlier one's, which
    // flipped whether an edge authored against the earlier assessment fired.
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        // jealousy's own security reading is low — this should fire the
        // jealousy -> intimacy edge below regardless of what love's own
        // security score happens to be.
        scores: { security: 38 },
        recommendedNext: [
          { assessmentSlug: "intimacy", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
        ],
      },
      {
        slug: "love",
        // love's own security reading is high — must not suppress the
        // jealousy edge above just because both assessments share the key.
        scores: { security: 67 },
        recommendedNext: [
          { assessmentSlug: "relationship", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
        ],
      },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    const intimacy = result.find((r) => r.slug === "intimacy")!;
    const relationship = result.find((r) => r.slug === "relationship")!;
    expect(intimacy.relevanceScore).toBe(1);
    expect(relationship.relevanceScore).toBe(0); // love's own security (67) doesn't satisfy its own [0,50] edge
  });

  it("sums weight when multiple completed assessments independently point at the same candidate", () => {
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        scores: { security: 30 },
        recommendedNext: [
          { assessmentSlug: "intimacy", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
        ],
      },
      {
        slug: "hidden-self",
        scores: { trust: 20 },
        recommendedNext: [
          { assessmentSlug: "intimacy", condition: { dimensionRanges: { trust: [0, 50] } }, weight: 0.5, bridgeCopy: "" },
        ],
      },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    expect(result.find((r) => r.slug === "intimacy")!.relevanceScore).toBe(1.5);
  });

  it("never recommends an already-completed assessment, even if an edge points at it", () => {
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        scores: { security: 10 },
        recommendedNext: [
          { assessmentSlug: "love", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
        ],
      },
      { slug: "love", scores: {}, recommendedNext: [] },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    expect(result.find((r) => r.slug === "love")!.relevanceScore).toBe(0);
  });

  it("ignores edges pointing at an assessment slug that isn't published", () => {
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        scores: { security: 10 },
        recommendedNext: [
          { assessmentSlug: "not-a-real-slug", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
        ],
      },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    expect(result.map((r) => r.slug)).not.toContain("not-a-real-slug");
  });

  it("orders not-yet-completed items ahead of completed ones, then by relevance descending", () => {
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        scores: { security: 10 },
        recommendedNext: [
          { assessmentSlug: "intimacy", condition: { dimensionRanges: { security: [0, 50] } }, weight: 1, bridgeCopy: "" },
          { assessmentSlug: "relationship", condition: { dimensionRanges: { security: [0, 50] } }, weight: 0.4, bridgeCopy: "" },
        ],
      },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    const order = result.map((r) => r.slug);
    expect(order.indexOf("intimacy")).toBeLessThan(order.indexOf("relationship"));
    expect(order.indexOf("relationship")).toBeLessThan(order.indexOf("jealousy")); // completed sinks to the end
  });

  it("treats a missing dimension key in scores as neutral (50), matching the AI-report-engine convention", () => {
    const completed: CompletedAssessmentInput[] = [
      {
        slug: "jealousy",
        scores: {}, // no reading at all for "security"
        recommendedNext: [
          { assessmentSlug: "intimacy", condition: { dimensionRanges: { security: [40, 60] } }, weight: 1, bridgeCopy: "" },
        ],
      },
    ];

    const result = rankBySlugWeights({ publishedSlugs, completed });
    expect(result.find((r) => r.slug === "intimacy")!.relevanceScore).toBe(1); // default 50 falls inside [40,60]
  });
});
