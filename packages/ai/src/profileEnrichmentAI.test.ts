import { describe, expect, it } from "vitest";
import { enrichProfileWithAI, type DimensionInput, type TensionInput } from "./profileEnrichmentAI";

const dimensions: DimensionInput[] = [
  { key: "connection", label: "Connection", normalized: 82, confidence: 0.9 },
  { key: "independence", label: "Independence", normalized: 78, confidence: 0.8 },
  { key: "trust", label: "Trust", normalized: 25, confidence: 0.6 },
];

describe("enrichProfileWithAI fallback (no ANTHROPIC_API_KEY)", () => {
  it("is never null and always returns a structured, non-empty enrichment", async () => {
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: ["The Careful Opener"],
      dimensions,
      tensions: [],
      openAnswerThemes: [],
    });
    expect(result).toBeTruthy();
    expect(result.aiGenerated).toBe(false);
    expect(Array.isArray(result.themes)).toBe(true);
    expect(result.insights.length).toBeGreaterThan(0);
  });

  it("surfaces the highest-scoring dimension as a strength insight", async () => {
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: [],
      dimensions,
      tensions: [],
      openAnswerThemes: [],
    });
    const strength = result.insights.find((i) => i.type === "strength");
    expect(strength).toBeDefined();
    expect(strength!.text.toLowerCase()).toContain("connection");
    expect(strength!.confidence).toBe(0.9); // carries the dimension's own confidence, not a made-up number
  });

  it("surfaces the lowest-scoring dimension as a friction insight", async () => {
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: [],
      dimensions,
      tensions: [],
      openAnswerThemes: [],
    });
    const friction = result.insights.find((i) => i.type === "friction");
    expect(friction).toBeDefined();
    expect(friction!.text.toLowerCase()).toContain("trust");
  });

  it("surfaces a detected tension as a pattern insight, carrying its strength as confidence", async () => {
    const tensions: TensionInput[] = [{ key: "conn_indep", label: "connection and independence", dimensions: ["connection", "independence"], strength: 0.73 }];
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: [],
      dimensions,
      tensions,
      openAnswerThemes: [],
    });
    const pattern = result.insights.find((i) => i.type === "pattern");
    expect(pattern).toBeDefined();
    expect(pattern!.confidence).toBe(0.73);
  });

  it("uses open-answer themes when present instead of deriving generic ones", async () => {
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: [],
      dimensions,
      tensions: [],
      openAnswerThemes: ["protects-independence", "fears-rejection"],
    });
    expect(result.themes).toEqual(["protects-independence", "fears-rejection"]);
  });

  it("never produces diagnostic or clinical language (deterministic templates are hand-written, but this guards regressions)", async () => {
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Independent Connector",
      secondaryProfileNames: [],
      dimensions,
      tensions: [],
      openAnswerThemes: [],
    });
    const bannedTerms = ["disorder", "diagnosis", "syndrome", "narcissistic", "codependent", "you are", "you have"];
    for (const insight of result.insights) {
      for (const term of bannedTerms) {
        expect(insight.text.toLowerCase()).not.toContain(term);
      }
    }
  });

  it("degrades gracefully with no strong/weak dimensions and no tensions — still returns a valid shape", async () => {
    const neutralDimensions: DimensionInput[] = [{ key: "connection", label: "Connection", normalized: 50, confidence: 0.5 }];
    const result = await enrichProfileWithAI({
      primaryProfileName: "The Balanced Connector",
      secondaryProfileNames: [],
      dimensions: neutralDimensions,
      tensions: [],
      openAnswerThemes: [],
    });
    expect(result.aiGenerated).toBe(false);
    expect(Array.isArray(result.insights)).toBe(true);
    expect(Array.isArray(result.themes)).toBe(true);
  });
});
