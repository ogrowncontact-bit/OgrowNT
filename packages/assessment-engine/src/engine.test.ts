import { describe, expect, it } from "vitest";
import { startSession, nextQuestion, submitAnswer, computeResult } from "./engine";
import { recomputeDimensionScores } from "./scoring";
import type { AssessmentConfig, RecordedAnswer } from "./types";

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
  recommendedQuestions: 4,
  maxQuestions: 6,
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
      {
        key: "q3_open",
        type: "open_text",
        isCore: true,
        prompt: "Tell us more?",
        dynamicFollowupCandidates: ["ai_followup"],
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
      {
        key: "ai_followup",
        type: "single_select",
        isCore: false,
        prompt: "AI-chosen followup?",
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
    {
      key: "ai_dynamic_followup",
      trigger: { questionKey: "q3_open", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
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

  it("honors an AI-chosen follow-up baked into a recorded open-text answer", () => {
    let state = startSession(config);
    let result = submitAnswer(config, state, { questionKey: "q1", selectedOptionKeys: ["b"] });
    state = result.state;
    result = submitAnswer(config, state, { questionKey: "q2", selectedOptionKeys: ["b"] });
    state = result.state;
    // The caller (apps/web) resolves Question AI's choice *before* calling submitAnswer —
    // the engine just has to honor whatever was baked into the recorded answer.
    result = submitAnswer(config, state, {
      questionKey: "q3_open",
      openText: "some reflective answer",
      aiChosenFollowupKey: "ai_followup",
    });
    expect(result.nextQuestion?.key).toBe("ai_followup");
    expect(result.isComplete).toBe(false);
  });

  it("ignores an AI-chosen follow-up that was already asked (no infinite loop)", () => {
    let state = startSession(config);
    let result = submitAnswer(config, state, { questionKey: "q1", selectedOptionKeys: ["b"] });
    state = result.state;
    result = submitAnswer(config, state, { questionKey: "q2", selectedOptionKeys: ["b"] });
    state = result.state;
    result = submitAnswer(config, state, { questionKey: "ai_followup", selectedOptionKeys: ["a"] });
    state = result.state;
    // q3_open is still the next unanswered core question; even if something (bug, replay)
    // tried to point back at ai_followup, the engine's de-dup would ignore it.
    result = submitAnswer(config, state, {
      questionKey: "q3_open",
      openText: "some reflective answer",
      aiChosenFollowupKey: "ai_followup", // already asked above
    });
    expect(result.nextQuestion?.key).not.toBe("ai_followup");
  });
});

describe("AI dimension nudges (scoring)", () => {
  const allQuestions = [...config.questionBank.core, ...config.questionBank.adaptivePool];

  it("shifts a score by at most aiInfluenceCap when no structured signal exists", () => {
    const scores = recomputeDimensionScores(config, allQuestions, [
      {
        questionKey: "q3_open",
        openText: "test",
        aiDimensionNudges: { connection: 1 }, // maximal nudge
        answeredAt: new Date().toISOString(),
      },
    ]);
    // baseline 50 (no structured contribution) + 1 * aiInfluenceCap(0.15) * 100 = 65
    expect(scores.connection.normalized).toBeCloseTo(65, 5);
  });

  it("never lets a nudge count toward confidence", () => {
    const scores = recomputeDimensionScores(config, allQuestions, [
      {
        questionKey: "q3_open",
        openText: "test",
        aiDimensionNudges: { connection: 1 },
        answeredAt: new Date().toISOString(),
      },
    ]);
    expect(scores.connection.confidence).toBe(0);
  });

  it("clamps out-of-range nudges defensively", () => {
    const scores = recomputeDimensionScores(config, allQuestions, [
      {
        questionKey: "q3_open",
        openText: "test",
        aiDimensionNudges: { connection: 999 }, // a misbehaving model shouldn't blow past the cap
        answeredAt: new Date().toISOString(),
      },
    ]);
    expect(scores.connection.normalized).toBeCloseTo(65, 5);
  });
});

describe("session persistence — replay determinism", () => {
  // apps/web never stores "current question" as its own field — it reconstructs
  // a session purely by replaying the stored answer rows back through
  // submitAnswer (see lib/sessionState.ts). That's only safe if doing so is
  // deterministic: the same answer sequence must always rebuild the exact
  // same state and land on the exact same next question, whether computed
  // live in one pass or replayed one answer at a time after a refresh/return.
  it("replaying stored answers one at a time reconstructs the same state as the live session", () => {
    const answersInOrder: { questionKey: string; selectedOptionKeys?: string[]; openText?: string; aiChosenFollowupKey?: string }[] = [
      { questionKey: "q1", selectedOptionKeys: ["b"] },
      { questionKey: "q2", selectedOptionKeys: ["b"] },
      { questionKey: "q3_open", openText: "reflective answer", aiChosenFollowupKey: "ai_followup" },
    ];

    let live = startSession(config);
    for (const input of answersInOrder) live = submitAnswer(config, live, input).state;

    // Simulate "user closed the browser and came back" — rebuild from scratch
    // by replaying the same recorded answers through a fresh session.
    let replayed = startSession(config);
    for (const input of answersInOrder) replayed = submitAnswer(config, replayed, input).state;

    // submitAnswer always stamps its own answeredAt at call time (apps/web's
    // reconstructSessionState passes the real stored timestamp in, but
    // submitAnswer doesn't accept/use it — see AnswerInput — so it's not
    // part of the determinism guarantee here). Compare the fields that
    // actually drive scoring and branching, which is what "replay is safe"
    // really means.
    expect(replayed.askedQuestionKeys).toEqual(live.askedQuestionKeys);
    expect(replayed.dimensionScores).toEqual(live.dimensionScores);
    expect(replayed.status).toEqual(live.status);
    expect(nextQuestion(config, replayed)?.key).toBe(nextQuestion(config, live)?.key);
  });

  it("reconstructed state produces the same completed profile as the original run", () => {
    let state = startSession(config);
    const steps: RecordedAnswer[] = [
      { questionKey: "q1", selectedOptionKeys: ["a"], answeredAt: "" },
      { questionKey: "followup", selectedOptionKeys: ["a"], answeredAt: "" },
    ];
    for (const s of steps) state = submitAnswer(config, state, s).state;
    const original = computeResult(config, state);

    let rebuilt = startSession(config);
    for (const s of steps) rebuilt = submitAnswer(config, rebuilt, s).state;
    const replayedResult = computeResult(config, rebuilt);

    expect(replayedResult.profileResult.primary.key).toBe(original.profileResult.primary.key);
    expect(replayedResult.dimensionScores).toEqual(original.dimensionScores);
  });
});
