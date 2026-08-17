import { describe, expect, it } from "vitest";
import { explainProfileMatch, matchProfiles, rankProfiles } from "./profileMatcher";
import type { AssessmentConfig, DimensionState, ProfileDefinition } from "./types";

function scores(overrides: Record<string, number>): Record<string, DimensionState> {
  const out: Record<string, DimensionState> = {};
  for (const [key, normalized] of Object.entries(overrides)) {
    out[key] = { raw: 0, normalized, confidence: 1 };
  }
  return out;
}

function config(profiles: ProfileDefinition[]): AssessmentConfig {
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
    dimensions: [{ key: "connection", weight: 1 }, { key: "independence", weight: 1 }, { key: "validation", weight: 1 }],
    scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },
    questionBank: { core: [], adaptivePool: [] },
    adaptiveRules: [],
    profiles,
    freeResultTemplate: { headline: "", insightIntro: "", lockedInsightsLabel: "" },
    premiumReportStructure: [],
    recommendedNext: [],
    pricing: {},
  };
}

describe("profile classification — required conditions", () => {
  // Message 2's own worked examples.
  it("Case A: high connection + high independence -> Independent Connector", () => {
    const c = config([
      { key: "independent_connector", name: "Independent Connector", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [70, 100], independence: [70, 100] } } },
      { key: "reassurance_seeker", name: "Reassurance Seeker", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [70, 100], validation: [70, 100] } } },
    ]);
    const result = matchProfiles(c, scores({ connection: 85, independence: 80, validation: 30 }));
    expect(result.primary.key).toBe("independent_connector");
  });

  it("Case B: high connection + high validation + low independence -> Reassurance Seeker", () => {
    const c = config([
      { key: "independent_connector", name: "Independent Connector", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [70, 100], independence: [70, 100] } } },
      { key: "reassurance_seeker", name: "Reassurance Seeker", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [70, 100], validation: [70, 100] } } },
    ]);
    const result = matchProfiles(c, scores({ connection: 85, independence: 25, validation: 78 }));
    expect(result.primary.key).toBe("reassurance_seeker");
  });
});

describe("profile classification — optional conditions distinguish similar profiles", () => {
  it("prefers the profile whose optional conditions are also satisfied when both required sets match", () => {
    const c = config([
      {
        key: "plain_connector",
        name: "Plain Connector",
        descriptionTemplate: "",
        matchingRule: { dimensionRanges: { connection: [60, 100] } },
      },
      {
        key: "deep_connector",
        name: "Deep Connector",
        descriptionTemplate: "",
        matchingRule: { dimensionRanges: { connection: [60, 100] }, optionalConditions: { validation: [60, 100] } },
      },
    ]);
    const result = matchProfiles(c, scores({ connection: 85, independence: 50, validation: 80 }));
    expect(result.primary.key).toBe("deep_connector");
  });
});

describe("profile classification — exclusion conditions", () => {
  it("disqualifies a profile whose exclude condition holds even though required ranges match", () => {
    const c = config([
      {
        key: "self_protector",
        name: "Self-Protector",
        descriptionTemplate: "",
        matchingRule: { dimensionRanges: { independence: [60, 100] }, excludeConditions: { connection: [70, 100] } },
      },
      {
        key: "independent_connector",
        name: "Independent Connector",
        descriptionTemplate: "",
        matchingRule: { dimensionRanges: { independence: [60, 100] } },
      },
    ]);
    // independence qualifies self_protector, but connection is high — excluded, falls through to the other match.
    const result = matchProfiles(c, scores({ connection: 90, independence: 75, validation: 50 }));
    expect(result.primary.key).toBe("independent_connector");
  });
});

describe("profile classification — priority tie-break", () => {
  it("uses priority when two profiles match required conditions with an equal optional-condition count", () => {
    const c = config([
      { key: "low_priority", name: "Low", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [60, 100] } }, priority: 1 },
      { key: "high_priority", name: "High", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [60, 100] } }, priority: 5 },
    ]);
    const result = matchProfiles(c, scores({ connection: 85, independence: 50, validation: 50 }));
    expect(result.primary.key).toBe("high_priority");
  });
});

describe("secondary patterns", () => {
  it("ranks non-primary profiles as secondary, closest first", () => {
    const c = config([
      { key: "a", name: "A", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [80, 100] } } },
      { key: "b", name: "B", descriptionTemplate: "", matchingRule: { dimensionRanges: { independence: [40, 60] } } },
      { key: "c", name: "C", descriptionTemplate: "", matchingRule: { dimensionRanges: { validation: [0, 10] } } },
    ]);
    const result = matchProfiles(c, scores({ connection: 90, independence: 50, validation: 50 }));
    expect(result.primary.key).toBe("a");
    expect(result.secondary.map((p) => p.key)).toEqual(["b", "c"]);
  });
});

describe("fallback when nothing matches exactly", () => {
  it("still lands on the closest profile by distance rather than leaving no primary", () => {
    const c = config([
      { key: "high_connection", name: "High", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [80, 100] } } },
      { key: "low_connection", name: "Low", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [0, 20] } } },
    ]);
    const result = matchProfiles(c, scores({ connection: 55, independence: 50, validation: 50 })); // matches neither range
    expect(["high_connection", "low_connection"]).toContain(result.primary.key);
  });
});

describe("explainability", () => {
  it("traces exactly which conditions passed and failed for the primary profile", () => {
    const c = config([
      {
        key: "independent_connector",
        name: "Independent Connector",
        descriptionTemplate: "",
        matchingRule: { dimensionRanges: { connection: [70, 100], independence: [70, 100] }, excludeConditions: { validation: [90, 100] } },
      },
    ]);
    const explanation = explainProfileMatch(c, scores({ connection: 85, independence: 80, validation: 30 }));
    const primary = explanation.find((e) => e.isPrimary)!;
    expect(primary.satisfiesRequired).toBe(true);
    expect(primary.isExcluded).toBe(false);
    expect(primary.required).toEqual([
      { dimensionKey: "connection", range: [70, 100], score: 85, satisfied: true },
      { dimensionKey: "independence", range: [70, 100], score: 80, satisfied: true },
    ]);
    expect(primary.excluded).toEqual([{ dimensionKey: "validation", range: [90, 100], score: 30, satisfied: false }]);
  });

  it("rankProfiles output is consistent with matchProfiles' primary/secondary selection", () => {
    const c = config([
      { key: "a", name: "A", descriptionTemplate: "", matchingRule: { dimensionRanges: { connection: [80, 100] } } },
      { key: "b", name: "B", descriptionTemplate: "", matchingRule: { dimensionRanges: { independence: [40, 60] } } },
    ]);
    const s = scores({ connection: 90, independence: 50, validation: 50 });
    const ranked = rankProfiles(c, s);
    const matched = matchProfiles(c, s);
    expect(ranked[0].profile.key).toBe(matched.primary.key);
  });
});
