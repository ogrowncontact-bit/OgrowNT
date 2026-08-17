import { describe, expect, it } from "vitest";
import { interpretOpenAnswer } from "./responseAI";

describe("interpretOpenAnswer fallback confidence (no ANTHROPIC_API_KEY)", () => {
  it("gives a longer, more detailed answer higher heuristic confidence than a one-word answer", async () => {
    const short = await interpretOpenAnswer({
      questionPrompt: "Tell us about a time you pulled away.",
      answerText: "Sometimes.",
      allowedDimensions: ["independence", "connection"],
    });
    const long = await interpretOpenAnswer({
      questionPrompt: "Tell us about a time you pulled away.",
      answerText:
        "There was a period where things were getting close very quickly and I noticed myself making excuses to " +
        "spend less time together, even though I still cared — I think I needed room to feel like myself again.",
      allowedDimensions: ["independence", "connection"],
    });
    expect(long.confidence).toBeGreaterThan(short.confidence);
  });

  it("never reports confidence outside 0..1", async () => {
    const result = await interpretOpenAnswer({
      questionPrompt: "?",
      answerText: "a".repeat(500), // long enough to try to blow past any naive cap
      allowedDimensions: ["independence"],
    });
    expect(result.confidence).toBeGreaterThanOrEqual(0);
    expect(result.confidence).toBeLessThanOrEqual(1);
  });

  it("caps the non-AI heuristic well below full confidence — it's a heuristic, not a real reading", async () => {
    const result = await interpretOpenAnswer({
      questionPrompt: "?",
      answerText: "word ".repeat(200),
      allowedDimensions: ["independence"],
    });
    expect(result.confidence).toBeLessThanOrEqual(0.5);
    expect(result.aiGenerated).toBe(false);
  });

  it("gives an empty answer zero confidence", async () => {
    const result = await interpretOpenAnswer({ questionPrompt: "?", answerText: "   ", allowedDimensions: [] });
    expect(result.confidence).toBe(0);
  });
});
