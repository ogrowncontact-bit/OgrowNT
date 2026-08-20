import { describe, expect, it } from "vitest";
import { generateReport, deriveStrengthsAndFriction, type ReportContext } from "./reportAI";

const sections = [
  { key: "signature", title: "Your INNER Signature" },
  { key: "dominant_pattern", title: "Your Dominant Pattern" },
  { key: "strengths", title: "Your Strengths" },
  { key: "friction_points", title: "Your Potential Friction Points" },
  { key: "inner_tension", title: "The Tension Inside Your Profile" },
];

function baseContext(overrides: Partial<ReportContext> = {}): ReportContext {
  return {
    assessmentName: "How Do You Love?",
    assessmentVersion: 2,
    primaryProfileName: "The Independent Connector",
    primaryProfileDescription: "Values closeness while protecting independence.",
    secondaryProfileNames: ["The Deep Connector"],
    dimensionScores: { connection: 82, independence: 79, trust: 55, vulnerability: 30 },
    dimensionConfidence: { connection: 1, independence: 0.8, trust: 0.5, vulnerability: 0.3 },
    dimensionLabels: { connection: "Connection", independence: "Independence", trust: "Trust", vulnerability: "Vulnerability" },
    tensions: [],
    contradictions: [],
    openAnswerThemes: [],
    language: "en",
    reportType: "individual",
    sections,
    ...overrides,
  };
}

describe("generateReport fallback (no ANTHROPIC_API_KEY)", () => {
  it("produces a non-empty body for every requested section", async () => {
    const result = await generateReport(baseContext());
    expect(result.sections).toHaveLength(sections.length);
    for (const section of result.sections) {
      expect(section.body.trim().length).toBeGreaterThan(0);
      expect(section.aiGenerated).toBe(false);
    }
  });

  it("reports its own engine/prompt versioning", async () => {
    const result = await generateReport(baseContext());
    expect(result.reportEngineVersion).toBeGreaterThan(0);
    expect(result.promptVersion).toBeGreaterThan(0);
    expect(result.modelVersion).toBe("none");
  });

  it("echoes back the generic persona's version (0) when no persona is passed", async () => {
    const result = await generateReport(baseContext());
    expect(result.personaVersion).toBe(0);
  });

  it("produces 4-6 non-empty, session-specific reflection questions even in fallback mode", async () => {
    const result = await generateReport(baseContext());
    expect(result.reflectionQuestions.length).toBeGreaterThanOrEqual(4);
    expect(result.reflectionQuestions.length).toBeLessThanOrEqual(6);
    for (const q of result.reflectionQuestions) expect(q.trim().length).toBeGreaterThan(0);
    // parameterized by this session's own top dimension, not generic filler
    expect(result.reflectionQuestions.some((q) => q.toLowerCase().includes("connection"))).toBe(true);
  });

  it("echoes back a real persona's version when one is passed, even in fallback mode", async () => {
    const result = await generateReport(baseContext(), undefined, {
      assessmentSlug: "love",
      name: "The Relationship Observer",
      focus: "connection and independence",
      prompt: "You notice the quiet negotiation between closeness and autonomy.",
      tone: { warmth: 0.8, directness: 0.4, depth: 0.7, formality: 0.25 },
      version: 5,
    });
    expect(result.personaVersion).toBe(5);
  });

  it("falls back to English when an unsupported language is requested", async () => {
    const result = await generateReport(baseContext({ language: "de" }));
    expect(result.language).toBe("en");
  });

  it("keeps a supported language through to the result even without AI", async () => {
    const result = await generateReport(baseContext({ language: "es" }));
    expect(result.language).toBe("es");
  });

  it("produces genuinely different narratives for different dimension scores under the same profile name", async () => {
    const resultA = await generateReport(
      baseContext({ dimensionScores: { connection: 90, independence: 20, trust: 80, vulnerability: 70 } })
    );
    const resultB = await generateReport(
      baseContext({ dimensionScores: { connection: 20, independence: 90, trust: 30, vulnerability: 20 } })
    );
    const signatureA = resultA.sections.find((s) => s.key === "dominant_pattern")!.body;
    const signatureB = resultB.sections.find((s) => s.key === "dominant_pattern")!.body;
    expect(signatureA).not.toBe(signatureB);
  });

  it("surfaces a detected tension in the inner_tension section", async () => {
    const result = await generateReport(
      baseContext({ tensions: [{ label: "wanting closeness and strongly protecting independence", strength: 0.8 }] })
    );
    const tensionSection = result.sections.find((s) => s.key === "inner_tension")!;
    expect(tensionSection.body).toContain("wanting closeness and strongly protecting independence");
  });

  it("names no tension when none was detected", async () => {
    const result = await generateReport(baseContext({ tensions: [] }));
    const tensionSection = result.sections.find((s) => s.key === "inner_tension")!;
    expect(tensionSection.body.toLowerCase()).toContain("didn't reveal");
  });

  it("surfaces a detected contradiction in the inner_tension section, framed as situational rather than a flaw", async () => {
    const result = await generateReport(
      baseContext({ contradictions: [{ label: "openness in conflict", strength: 0.5 }] })
    );
    const tensionSection = result.sections.find((s) => s.key === "inner_tension")!;
    expect(tensionSection.body.toLowerCase()).toContain("openness in conflict");
    expect(tensionSection.body.toLowerCase()).toContain("depends on the situation");
  });

  it("mentions both a tension and a contradiction when both are detected, distinctly", async () => {
    const result = await generateReport(
      baseContext({
        tensions: [{ label: "wanting closeness and strongly protecting independence", strength: 0.8 }],
        contradictions: [{ label: "openness in conflict", strength: 0.5 }],
      })
    );
    const tensionSection = result.sections.find((s) => s.key === "inner_tension")!;
    expect(tensionSection.body).toContain("wanting closeness and strongly protecting independence");
    expect(tensionSection.body.toLowerCase()).toContain("openness in conflict");
  });
});

describe("deriveStrengthsAndFriction", () => {
  it("labels dimensions at or above 65 as strengths and at or below 35 as friction", () => {
    const { strengths, friction } = deriveStrengthsAndFriction(
      { connection: 82, independence: 79, trust: 50, vulnerability: 20 },
      { connection: "Connection", independence: "Independence", trust: "Trust", vulnerability: "Vulnerability" }
    );
    expect(strengths).toEqual(["Connection", "Independence"]);
    expect(friction).toEqual(["Vulnerability"]);
  });

  it("caps each list at 3 entries", () => {
    const { strengths } = deriveStrengthsAndFriction({ a: 90, b: 88, c: 86, d: 84 });
    expect(strengths).toHaveLength(3);
  });
});
