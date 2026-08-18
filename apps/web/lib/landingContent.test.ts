import { describe, expect, it } from "vitest";
import type { AssessmentConfig } from "@inner/assessment-engine";
import { getDiscoveryPoints, getFaqItems } from "./landingContent";

function makeConfig(overrides: Partial<AssessmentConfig> = {}): AssessmentConfig {
  return {
    slug: "test-assessment",
    name: "Your Test Pattern",
    category: "test",
    description: "A short, adaptive conversation about testing.",
    hook: "Some hook.",
    targetAudience: "everyone",
    dimensions: [],
    questionBank: { core: [], adaptivePool: [] },
    adaptiveRules: [],
    scoringModel: { normalization: "min-max", aiInfluenceCap: 0.3 },
    profiles: [],
    freeResultTemplate: { headline: "", insightIntro: "", lockedInsightsLabel: "" },
    premiumReportStructure: [
      { key: "specific_one", title: "Specific Section One", promptRef: "p1" },
      { key: "specific_two", title: "Specific Section Two", promptRef: "p2" },
      { key: "specific_three", title: "Specific Section Three", promptRef: "p3" },
      { key: "signature", title: "Your Signature", promptRef: "p4" },
    ],
    recommendedNext: [],
    pricing: {},
    status: "published",
    version: 1,
    minQuestions: 10,
    recommendedQuestions: 15,
    maxQuestions: 20,
    ...overrides,
  };
}

describe("getFaqItems", () => {
  it("phrases the first question with quotes, no doubled punctuation, for a name ending in '?'", () => {
    const config = makeConfig({ name: "How Do You Love?" });
    expect(getFaqItems(config)[0].question).toBe('What is "How Do You Love?"');
  });

  it("phrases the first question naturally for a name starting with 'Your'", () => {
    const config = makeConfig({ name: "Your Relationship Pattern" });
    expect(getFaqItems(config)[0].question).toBe('What is "Your Relationship Pattern"?');
  });

  it("uses the assessment's own description and question count", () => {
    const config = makeConfig({ description: "Real description.", recommendedQuestions: 22 });
    const items = getFaqItems(config);
    expect(items[0].answer).toBe("Real description.");
    expect(items[1].answer).toContain("22 questions");
  });
});

describe("getDiscoveryPoints", () => {
  it("prefers assessment-specific sections over generic wrap-up ones", () => {
    const config = makeConfig();
    const points = getDiscoveryPoints(config).map((p) => p.title);
    expect(points).toEqual(["Specific Section One", "Specific Section Two", "Specific Section Three"]);
  });

  it("falls back to the full report structure when fewer than 3 specific sections exist", () => {
    const config = makeConfig({
      premiumReportStructure: [
        { key: "signature", title: "Your Signature", promptRef: "p1" },
        { key: "strengths", title: "Your Strengths", promptRef: "p2" },
      ],
    });
    const points = getDiscoveryPoints(config).map((p) => p.title);
    expect(points).toEqual(["Your Signature", "Your Strengths"]);
  });
});
