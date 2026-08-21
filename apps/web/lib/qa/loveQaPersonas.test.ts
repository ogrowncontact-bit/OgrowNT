import { describe, expect, it } from "vitest";
import { generateLoveQaPersonas } from "./loveQaPersonas";

describe("generateLoveQaPersonas", () => {
  it("generates exactly the requested count", () => {
    expect(generateLoveQaPersonas(100)).toHaveLength(100);
    expect(generateLoveQaPersonas(30)).toHaveLength(30);
  });

  it("produces unique persona keys", () => {
    const personas = generateLoveQaPersonas(100);
    const keys = new Set(personas.map((p) => p.key));
    expect(keys.size).toBe(personas.length);
  });

  it("produces unique target-direction signatures (no duplicate personas)", () => {
    const personas = generateLoveQaPersonas(100);
    const signatures = new Set(personas.map((p) => JSON.stringify(Object.entries(p.targetDirections).sort())));
    expect(signatures.size).toBe(personas.length);
  });

  it("is deterministic across calls (same seed)", () => {
    const a = generateLoveQaPersonas(100);
    const b = generateLoveQaPersonas(100);
    expect(a).toEqual(b);
  });

  it("includes at least one solo-high and solo-low persona per LOVE dimension", () => {
    const personas = generateLoveQaPersonas(100);
    const dims = ["connection", "independence", "trust", "vulnerability", "emotional_openness", "validation", "security", "conflict", "affection_expression", "distance_response"];
    for (const dim of dims) {
      expect(personas.some((p) => Object.keys(p.targetDirections).length === 1 && p.targetDirections[dim] === "high")).toBe(true);
      expect(personas.some((p) => Object.keys(p.targetDirections).length === 1 && p.targetDirections[dim] === "low")).toBe(true);
    }
  });

  it("includes at least one balanced (no target directions) persona", () => {
    const personas = generateLoveQaPersonas(100);
    expect(personas.some((p) => Object.keys(p.targetDirections).length === 0)).toBe(true);
  });
});
