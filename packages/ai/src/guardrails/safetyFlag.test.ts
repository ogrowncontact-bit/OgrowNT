import { describe, expect, it } from "vitest";
import { detectSafetyConcern } from "./safetyFlag";

describe("detectSafetyConcern", () => {
  const concerning = [
    "Sometimes I think about ending my life when it gets bad.",
    "I've been having suicidal thoughts lately.",
    "I've been self-harming when I feel this way.",
    "Honestly I just don't want to be alive anymore.",
    "My partner hits me when we argue and I don't know what to do.",
    "I'm being abused and I'm scared to leave.",
  ];

  const notConcerning = [
    "We were getting close fast and I found myself pulling back even though I wanted to stay close.",
    "Sometimes I feel like disappearing for the weekend to clear my head.",
    "I get anxious before big conversations but it usually passes.",
    "My ex and I used to fight a lot about small things.",
    "I killed it at that presentation and felt on top of the world.",
  ];

  it.each(concerning)("flags: %s", (text) => {
    expect(detectSafetyConcern(text)).toBe(true);
  });

  it.each(notConcerning)("does not flag: %s", (text) => {
    expect(detectSafetyConcern(text)).toBe(false);
  });
});
