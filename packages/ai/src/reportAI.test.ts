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
