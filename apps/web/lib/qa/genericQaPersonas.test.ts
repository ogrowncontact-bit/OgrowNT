import { describe, expect, it } from "vitest";
import { generateQaPersonas } from "./genericQaPersonas";

// relationship's real 8 scored dimensions (packages/content/src/assessments/relationship.ts)
// — used here as a representative non-LOVE dimension set, distinct in both
// size and names from LOVE's 10, to exercise the generator's dimension-agnosticism.
const RELATIONSHIP_DIMENSIONS = [
  "connection",
  "security",
  "independence",
  "trust",
  "conflict",
  "communication",
  "emotional_openness",
  "expectations",
];

describe("generateQaPersonas", () => {
  it("generates exactly the requested count", () => {
    expect(generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100)).toHaveLength(100);
    expect(generateQaPersonas(RELATIONSHIP_DIMENSIONS, 30)).toHaveLength(30);
  });

  it("produces unique persona keys", () => {
    const personas = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    const keys = new Set(personas.map((p) => p.key));
    expect(keys.size).toBe(personas.length);
  });

  it("produces unique target-direction signatures (no duplicate personas)", () => {
    const personas = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    const signatures = new Set(personas.map((p) => JSON.stringify(Object.entries(p.targetDirections).sort())));
    expect(signatures.size).toBe(personas.length);
  });

  it("is deterministic across calls (same seed)", () => {
    const a = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    const b = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    expect(a).toEqual(b);
  });

  it("includes at least one solo-high and solo-low persona per dimension", () => {
    const personas = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    for (const dim of RELATIONSHIP_DIMENSIONS) {
      expect(personas.some((p) => Object.keys(p.targetDirections).length === 1 && p.targetDirections[dim] === "high")).toBe(true);
      expect(personas.some((p) => Object.keys(p.targetDirections).length === 1 && p.targetDirections[dim] === "low")).toBe(true);
    }
  });

  it("includes at least one balanced (no target directions) persona", () => {
    const personas = generateQaPersonas(RELATIONSHIP_DIMENSIONS, 100);
    expect(personas.some((p) => Object.keys(p.targetDirections).length === 0)).toBe(true);
  });

  it("works for a much smaller dimension set too (2 dimensions)", () => {
    const personas = generateQaPersonas(["a", "b"], 20);
    expect(personas.length).toBeGreaterThan(0);
    expect(personas.length).toBeLessThanOrEqual(20);
    // every target-direction dimension key actually belongs to the requested set
    for (const p of personas) {
      for (const dim of Object.keys(p.targetDirections)) {
        expect(["a", "b"]).toContain(dim);
      }
    }
  });
});
