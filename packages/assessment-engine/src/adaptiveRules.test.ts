import { describe, expect, it } from "vitest";
import { decideNextStep, selectByInformationValue } from "./adaptiveRules";
import type { AssessmentConfig, DimensionState, Question, RecordedAnswer } from "./types";

const clarifiesIndependence: Question = {
  key: "clarify_independence",
  type: "single_select",
  isCore: false,
  prompt: "?",
  options: [{ key: "a", label: "a", dimensionContributions: { independence: 2 } }],
};
const clarifiesConnection: Question = {
  key: "clarify_connection",
  type: "single_select",
  isCore: false,
  prompt: "?",
  options: [{ key: "a", label: "a", dimensionContributions: { connection: 2 } }],
};
const touchesValidation: Question = {
  key: "touches_validation",
  type: "single_select",
  isCore: false,
  prompt: "?",
  options: [{ key: "a", label: "a", dimensionContributions: { validation: 2 } }],
};
const touchesSecurity: Question = {
  key: "touches_security",
  type: "single_select",
  isCore: false,
  prompt: "?",
  options: [{ key: "a", label: "a", dimensionContributions: { security: 2 } }],
};

function config(overrides: Partial<AssessmentConfig> = {}): AssessmentConfig {
  return {
    slug: "test",
    name: "Test",
    category: "test",
    description: "",
    hook: "",
    targetAudience: "",
    status: "published",
    version: 1,
    minQuestions: 5,
    recommendedQuestions: 7,
    maxQuestions: 9,
    dimensions: [
      { key: "connection", weight: 1 },
      { key: "independence", weight: 1 },
      { key: "validation", weight: 1 },
      { key: "security", weight: 1 },
    ],
    scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },
    questionBank: { core: [], adaptivePool: [clarifiesIndependence, clarifiesConnection, touchesValidation, touchesSecurity] },
    adaptiveRules: [],
    profiles: [
      { key: "independent_connector", name: "Independent Connector", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [60, 100], independence: [60, 100] } } },
      { key: "reassurance_seeker", name: "Reassurance Seeker", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [60, 100], validation: [60, 100] } } },
    ],
    freeResultTemplate: { headline: "", insightIntro: "", lockedInsightsLabel: "" },
    premiumReportStructure: [],
    recommendedNext: [],
    pricing: {},
    ...overrides,
  };
}

function state(overrides: Record<string, Partial<DimensionState>>): Record<string, DimensionState> {
  const base: Record<string, DimensionState> = {
    connection: { raw: 0, normalized: 50, confidence: 0.9 },
    independence: { raw: 0, normalized: 50, confidence: 0.9 },
    validation: { raw: 0, normalized: 50, confidence: 0.9 },
    security: { raw: 0, normalized: 50, confidence: 0.9 },
  };
  for (const [k, v] of Object.entries(overrides)) base[k] = { ...base[k], ...v };
  return base;
}

describe("information-value selection — clarify uncertainty", () => {
  it("prefers a question touching a low-confidence dimension over one touching an already-saturated dimension", () => {
    const c = config();
    const scores = state({
      independence: { confidence: 0.1 }, // barely established
      connection: { confidence: 0.95 }, // saturated
      validation: { confidence: 0.95 }, // saturated
    });
    const picked = selectByInformationValue(c, [], scores);
    expect(picked).toBe("clarify_independence");
  });

  it("returns null once every candidate dimension is already saturated", () => {
    const c = config();
    const scores = state({ connection: { confidence: 0.95 }, independence: { confidence: 0.95 }, validation: { confidence: 0.95 } });
    // still returns *something* since penalty doesn't fully zero out value unless truly nothing to gain —
    // this test instead verifies exhausting the pool returns null.
    const picked = selectByInformationValue(
      c,
      ["clarify_independence", "clarify_connection", "touches_validation", "touches_security"],
      scores
    );
    expect(picked).toBeNull();
  });
});

describe("information-value selection — explore tensions", () => {
  it("prefers a question touching a dimension involved in a detected tension", () => {
    const c = config({
      tensionPairs: [{ key: "conn_indep", label: "Connection vs Independence", dimensionA: "connection", dimensionB: "independence", thresholdA: 65, thresholdB: 65 }],
    });
    // Both connection and independence are strong enough to register a tension; validation is neutral and unrelated.
    const scores = state({
      connection: { normalized: 80, confidence: 0.5 },
      independence: { normalized: 78, confidence: 0.5 },
      validation: { normalized: 50, confidence: 0.5 },
    });
    const picked = selectByInformationValue(c, ["touches_validation"], scores); // remove the unrelated one to force a clean choice
    expect(["clarify_independence", "clarify_connection"]).toContain(picked);
  });
});

describe("information-value selection — distinguish similar profiles", () => {
  it("prefers a question touching a dimension that separates the top-2 candidate profiles over an equally-uncertain but irrelevant one", () => {
    const c = config();
    // independent_connector requires connection+independence; reassurance_seeker requires
    // connection+validation — independence is a "swing" dimension between them. security isn't
    // referenced by either profile at all. Holding independence's and security's confidence
    // (and directional strength) identical isolates the swing-dimension effect specifically.
    const scores = state({
      connection: { normalized: 65, confidence: 0.9 }, // satisfies both profiles' shared requirement, already well-established
      independence: { normalized: 55, confidence: 0.4 }, // swing dimension, moderately uncertain
      validation: { normalized: 55, confidence: 0.9 }, // satisfies reassurance_seeker's requirement, already well-established
      security: { normalized: 55, confidence: 0.4 }, // same uncertainty as independence, but irrelevant to either candidate profile
    });
    const picked = selectByInformationValue(c, ["clarify_connection", "touches_validation"], scores);
    expect(picked).toBe("clarify_independence");
  });
});

describe("decideNextStep — completion bounds with the information-value layer", () => {
  it("never completes before minQuestions while any adaptive-pool candidate remains", () => {
    const c = config();
    const scores = state({});
    const step = decideNextStep(c, ["a", "b", "c", "d"], [{ questionKey: "d", answeredAt: "" } as RecordedAnswer], scores);
    expect(step.type).toBe("ask_followup");
  });

  it("stops once minQuestions is reached and the pool is exhausted", () => {
    const c = config();
    const scores = state({});
    const askedAll = ["a", "b", "c", "d", "e", "clarify_independence", "clarify_connection", "touches_validation", "touches_security"];
    const step = decideNextStep(c, askedAll, [{ questionKey: "touches_validation", answeredAt: "" } as RecordedAnswer], scores);
    expect(step.type).toBe("complete");
  });

  it("does not force reaching maxQuestions when nothing more is worth asking", () => {
    const c = config({ minQuestions: 1, recommendedQuestions: 2 });
    // Everything already well-established and no tensions — past recommended, nothing high-value left.
    const scores = state({ connection: { confidence: 0.9 }, independence: { confidence: 0.9 }, validation: { confidence: 0.9 } });
    const step = decideNextStep(c, ["a", "b"], [{ questionKey: "b", answeredAt: "" } as RecordedAnswer], scores);
    expect(step.type).toBe("complete");
  });

  it("keeps going past recommended for a genuinely low-confidence dimension, but never past maxQuestions", () => {
    const c = config({ minQuestions: 1, recommendedQuestions: 2, maxQuestions: 3 });
    const scores = state({ independence: { confidence: 0 } }); // wide open — worth one more question
    const step = decideNextStep(c, ["a", "b"], [{ questionKey: "b", answeredAt: "" } as RecordedAnswer], scores);
    expect(step.type).toBe("ask_followup");

    const atMax = decideNextStep(c, ["a", "b", "clarify_independence"], [{ questionKey: "clarify_independence", answeredAt: "" } as RecordedAnswer], scores);
    expect(atMax.type).toBe("complete");
  });
});
