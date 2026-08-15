import { describe, expect, it } from "vitest";
import { startSession, nextQuestion, submitAnswer, computeResult } from "./engine";
import type { AssessmentConfig } from "./types";

const config: AssessmentConfig = {
  slug: "test",
  name: "Test Assessment",
  category: "test",
  description: "",
  hook: "",
  targetAudience: "",
  status: "published",
  version: 1,
  minQuestions: 1,
  recommendedQuestions: 2,
  maxQuestions: 3,
  dimensions: [
    { key: "connection", weight: 1 },
    { key: "independence", weight: 1 },
  ],
  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },
  questionBank: {
    core: [
      {
        key: "q1",
        type: "single_select",
        isCore: true,
        prompt: "Q1?",
        options: [
          { key: "a", label: "A", dimensionContributions: { connection: 3 } },
          { key: "b", label: "B", dimensionContributions: { independence: 3 } },
        ],
      },
      {
        key: "q2",
        type: "single_select",
        isCore: true,
        prompt: "Q2?",
        options: [
          { key: "a", label: "A", dimensionContributions: { connection: 2 } },
          { key: "b", label: "B", dimensionContributions: { independence: 2 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "followup",
        type: "single_select",
        isCore: false,
        prompt: "Followup?",
        options: [{ key: "a", label: "A", dimensionContributions: { connection: 1 } }],
      },
    ],
  },
  adaptiveRules: [
    {
      key: "branch_on_a",
      trigger: { questionKey: "q1", op: "answered_option", optionKey: "a" },
      action: { type: "ask_followup", followupQuestionKey: "followup" },
      priority: 10,
    },
  ],
  profiles: [
    {
      key: "connector",
      name: "Connector",
      descriptionTemplate: "",
      matchingRule: { dimensionRanges: { connection: [60, 100] } },
    },
    {
      key: "independent",
      name: "Independent",
      descriptionTemplate: "",
      matchingRule: { dimensionRanges: { independence: [60, 100] } },
    },
  ],
  freeResultTemplate: { headline: "", insightIntro: "", lockedInsightsLabel: "" },
  premiumReportStructure: [],
  recommendedNext: [],
  pricing: {},
};

describe("assessment engine", () => {
  it("starts with the first core question", () => {
    const state = startSession(config);
    const q = nextQuestion(config, state);
    expect(q?.key).toBe("q1");
  });

  it("branches into an adaptive follow-up when a rule matches", () => {
    let state = startSession(config);
    const result = submitAnswer(config, state, { questionKey: "q1", selectedOptionKeys: ["a"] });
    state = result.state;
    expect(result.nextQuestion?.key).toBe("followup");
    expect(result.isComplete).toBe(false);
  });

  it("never exceeds maxQuestions", () => {
    let state = startSession(config);
    let asked = 0;
    let q = nextQuestion(config, state);
    while (q && asked < 10) {
      const result = submitAnswer(config, state, { questionKey: q.key, selectedOptionKeys: ["a"] });
      state = result.state;
      q = result.nextQuestion;
      asked += 1;
    }
    expect(asked).toBeLessThanOrEqual(config.maxQuestions);
    expect(state.status).toBe("completed");
  });

  it("computes normalized scores centered at 50 with no signal", () => {
    const state = startSession(config);
    const result = computeResult(config, state);
    expect(result.dimensionScores.connection.normalized).toBe(50);
  });

  it("matches a profile once a dimension score is strongly signaled", () => {
    let state = startSession(config);
    let result = submitAnswer(config, state, { questionKey: "q1", selectedOptionKeys: ["a"] });
    state = result.state;
    result = submitAnswer(config, state, { questionKey: "followup", selectedOptionKeys: ["a"] });
    state = result.state;
    const { profileResult } = computeResult(config, state);
    expect(profileResult.primary.key).toBe("connector");
  });
});
