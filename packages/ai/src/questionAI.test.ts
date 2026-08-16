import { describe, expect, it } from "vitest";
import { chooseFollowup } from "./questionAI";

describe("chooseFollowup fallback (no ANTHROPIC_API_KEY)", () => {
  const candidates = [
    { key: "what_would_help", prompt: "What do you think would help you stay close instead of pulling away?" },
    { key: "what_pattern_notice", prompt: "Looking back, is this a pattern you recognize in other relationships too?" },
  ];

  it("picks the candidate whose own prompt overlaps most with the answer text", async () => {
    const result = await chooseFollowup({
      answerText: "This keeps happening again and again, it's a pattern I recognize from every past relationship.",
      tags: [],
      candidates,
    });
    expect(result.chosenKey).toBe("what_pattern_notice");
    expect(result.aiGenerated).toBe(false);
  });

  it("falls back to the first candidate when there's no vocabulary signal", async () => {
    const result = await chooseFollowup({ answerText: "xyz", tags: [], candidates });
    expect(result.chosenKey).toBe(candidates[0].key);
  });

  it("returns the only candidate when just one is given, without scoring", async () => {
    const result = await chooseFollowup({ answerText: "anything at all", tags: [], candidates: [candidates[1]] });
    expect(result.chosenKey).toBe(candidates[1].key);
  });

  it("returns null when there are no candidates", async () => {
    const result = await chooseFollowup({ answerText: "anything", tags: [], candidates: [] });
    expect(result.chosenKey).toBeNull();
  });

  it("is generic across differently-named candidates (not hardcoded to /love's keys)", async () => {
    const relationshipCandidates = [
      { key: "what_triggers_pattern", prompt: "What usually triggers that pattern for you?" },
      { key: "how_pattern_started", prompt: "Does this feel like a pattern you learned early on, or something newer?" },
    ];
    const result = await chooseFollowup({
      answerText: "This goes way back to when I was a kid, it's something I learned early on.",
      tags: [],
      candidates: relationshipCandidates,
    });
    expect(result.chosenKey).toBe("how_pattern_started");
  });
});
