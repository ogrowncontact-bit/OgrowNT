import { describe, expect, it } from "vitest";
import { detectTensions, explainDimension, recomputeDimensionScores } from "./scoring";
import type { AssessmentConfig, Question, RecordedAnswer } from "./types";

const dims: AssessmentConfig["dimensions"] = [
  { key: "connection", weight: 1 },
  { key: "independence", weight: 1 },
];

function baseConfig(overrides: Partial<AssessmentConfig> = {}): AssessmentConfig {
  return {
    slug: "test",
    name: "Test",
    category: "test",
    description: "",
    hook: "",
    targetAudience: "",
    status: "published",
    version: 1,
    minQuestions: 1,
    recommendedQuestions: 4,
    maxQuestions: 6,
    dimensions: dims,
    scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },
    questionBank: { core: [], adaptivePool: [] },
    adaptiveRules: [],
    profiles: [],
    freeResultTemplate: { headline: "", insightIntro: "", lockedInsightsLabel: "" },
    premiumReportStructure: [],
    recommendedNext: [],
    pricing: {},
    ...overrides,
  };
}

const q: Question = {
  key: "q1",
  type: "single_select",
  isCore: true,
  prompt: "?",
  options: [
    { key: "pos", label: "pos", dimensionContributions: { connection: 3 } },
    { key: "neg", label: "neg", dimensionContributions: { connection: -3 } },
  ],
};

function answer(optionKey: string, questionKey = "q1"): RecordedAnswer {
  return { questionKey, selectedOptionKeys: [optionKey], answeredAt: new Date().toISOString() };
}

describe("confidence: volume + consistency", () => {
  it("grows with more contributing answers up to saturation", () => {
    const config = baseConfig();
    const one = recomputeDimensionScores(config, [q], [answer("pos")]);
    const three = recomputeDimensionScores(config, [q], [answer("pos"), answer("pos"), answer("pos")]);
    expect(three.connection.confidence).toBeGreaterThan(one.connection.confidence);
    expect(three.connection.confidence).toBe(1); // saturates at 3 fully-agreeing answers
  });

  it("dampens confidence when contributions disagree in direction", () => {
    const config = baseConfig();
    const agreeing = recomputeDimensionScores(config, [q], [answer("pos"), answer("pos"), answer("pos")]);
    const split = recomputeDimensionScores(config, [q], [answer("pos"), answer("pos"), answer("neg")]);
    // same count (3, saturated), but split 2/1 rather than 3/0 — consistency should be lower
    expect(split.connection.confidence).toBeLessThan(agreeing.connection.confidence);
    expect(split.connection.confidence).toBeCloseTo((2 / 3) * 1, 5); // 2 of 3 agree
  });

  it("never lets a perfectly even split reach full confidence even at high volume", () => {
    const config = baseConfig();
    const scores = recomputeDimensionScores(
      config,
      [q],
      [answer("pos"), answer("neg"), answer("pos"), answer("neg"), answer("pos"), answer("neg")]
    );
    expect(scores.connection.confidence).toBeCloseTo(0.5, 5); // count saturated (1.0) * consistency (0.5)
  });
});

describe("explainDimension", () => {
  it("traces a score back to the exact contributing answers", () => {
    const config = baseConfig();
    const explanation = explainDimension(config, [q], [answer("pos"), answer("neg"), answer("pos")], "connection");
    expect(explanation.count).toBe(3);
    expect(explanation.positiveCount).toBe(2);
    expect(explanation.negativeCount).toBe(1);
    expect(explanation.contributingAnswers).toHaveLength(3);
    expect(explanation.contributingAnswers[0]).toEqual({ questionKey: "q1", weight: 3 });
  });

  it("reports zero confidence and empty contributions for an unanswered dimension", () => {
    const config = baseConfig();
    const explanation = explainDimension(config, [q], [], "connection");
    expect(explanation.count).toBe(0);
    expect(explanation.confidence).toBe(0);
  });
});

describe("tension detection", () => {
  const withTensionPair = baseConfig({
    tensionPairs: [
      { key: "connection_independence", label: "Connection vs. Independence", dimensionA: "connection", dimensionB: "independence", thresholdA: 65, thresholdB: 65 },
    ],
  });

  it("does not register a tension when only one side is strong", () => {
    const scores = { connection: { raw: 0, normalized: 90, confidence: 1 }, independence: { raw: 0, normalized: 40, confidence: 1 } };
    expect(detectTensions(withTensionPair, scores)).toEqual([]);
  });

  it("registers a tension when both sides clear their threshold — this is a real coexisting pattern, not a contradiction", () => {
    const scores = { connection: { raw: 0, normalized: 82, confidence: 1 }, independence: { raw: 0, normalized: 79, confidence: 1 } };
    const tensions = detectTensions(withTensionPair, scores);
    expect(tensions).toHaveLength(1);
    expect(tensions[0].key).toBe("connection_independence");
    expect(tensions[0].dimensions).toEqual(["connection", "independence"]);
    expect(tensions[0].strength).toBeGreaterThan(0);
    expect(tensions[0].strength).toBeLessThanOrEqual(1);
  });

  it("strength increases the further both sides clear their thresholds", () => {
    const barely = detectTensions(withTensionPair, {
      connection: { raw: 0, normalized: 66, confidence: 1 },
      independence: { raw: 0, normalized: 66, confidence: 1 },
    })[0];
    const strong = detectTensions(withTensionPair, {
      connection: { raw: 0, normalized: 99, confidence: 1 },
      independence: { raw: 0, normalized: 99, confidence: 1 },
    })[0];
    expect(strong.strength).toBeGreaterThan(barely.strength);
  });

  it("detects no tensions for an assessment with no authored tensionPairs", () => {
    const config = baseConfig();
    const scores = { connection: { raw: 0, normalized: 99, confidence: 1 }, independence: { raw: 0, normalized: 99, confidence: 1 } };
    expect(detectTensions(config, scores)).toEqual([]);
  });

  it("supports a 'high on one side, low on the other' tension via directionB: lte", () => {
    // "I prefer complete independence" + "uncomfortable when someone becomes distant" —
    // not a contradiction, a real coexisting pattern: high independence, low tolerance
    // for distance (i.e. a *low* distance_response score).
    const c = baseConfig({
      dimensions: [{ key: "independence", weight: 1 }, { key: "distance_response", weight: 1 }],
      tensionPairs: [
        {
          key: "independence_low_distance_tolerance",
          label: "Independence and a low tolerance for distance",
          dimensionA: "independence",
          thresholdA: 70,
          dimensionB: "distance_response",
          thresholdB: 30,
          directionB: "lte",
        },
      ],
    });
    const noTension = detectTensions(c, {
      independence: { raw: 0, normalized: 85, confidence: 1 },
      distance_response: { raw: 0, normalized: 60, confidence: 1 }, // high tolerance — no tension
    });
    expect(noTension).toEqual([]);

    const tension = detectTensions(c, {
      independence: { raw: 0, normalized: 85, confidence: 1 },
      distance_response: { raw: 0, normalized: 15, confidence: 1 }, // low tolerance — tension
    });
    expect(tension).toHaveLength(1);
    expect(tension[0].strength).toBeGreaterThan(0);
  });
});
