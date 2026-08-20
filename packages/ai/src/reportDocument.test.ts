import { describe, expect, it } from "vitest";
import { generateReport, type ReportContext } from "./reportAI";
import { assembleReportDocument } from "./reportDocument";

const sections = [
  { key: "signature", title: "Your INNER Signature" },
  { key: "dominant_pattern", title: "Your Dominant Pattern" },
  { key: "strengths", title: "Your Strengths" },
  { key: "friction_points", title: "Your Potential Friction Points" },
  { key: "inner_tension", title: "The Tension Inside Your Profile" },
  { key: "reflection", title: "Your Personal Reflection" },
  { key: "final_note", title: "Final INNER Note" },
  { key: "how_you_connect", title: "How You Connect" }, // admin-authored custom key -> narrative role
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
    tensions: [{ label: "wanting closeness and protecting independence", strength: 0.7 }],
    contradictions: [],
    openAnswerThemes: [],
    language: "en",
    reportType: "individual",
    sections,
    ...overrides,
  };
}

describe("assembleReportDocument", () => {
  it("tags every section with a semantic role, including a narrative fallback for custom admin-authored keys", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const doc = assembleReportDocument({
      context,
      generated,
      assessmentSlug: "love",
      recommendation: { assessmentSlug: "intimacy", assessmentName: "How Deep Do You Go?", bridgeCopy: "Curious what's next?" },
    });

    const roleByKey = Object.fromEntries(doc.sections.map((s) => [s.key, s.role]));
    expect(roleByKey.signature).toBe("signature");
    expect(roleByKey.dominant_pattern).toBe("core_pattern");
    expect(roleByKey.strengths).toBe("strengths");
    expect(roleByKey.friction_points).toBe("friction");
    expect(roleByKey.inner_tension).toBe("tension");
    expect(roleByKey.reflection).toBe("reflection");
    expect(roleByKey.final_note).toBe("closing");
    expect(roleByKey.how_you_connect).toBe("narrative");
  });

  it("derives the summary from the signature section, without a second AI call", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation: null });
    expect(doc.summary).toBe(generated.sections.find((s) => s.key === "signature")!.body);
  });

  it("falls back to the profile description as the summary if no signature-role section exists", async () => {
    const context = baseContext({ sections: sections.filter((s) => s.key !== "signature") });
    const generated = await generateReport(context);
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation: null });
    expect(doc.summary).toBe(context.primaryProfileDescription);
  });

  it("carries dimension scores, labels, and confidence through structurally, independent of AI", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation: null });
    expect(doc.dimensions).toEqual([
      { key: "connection", label: "Connection", normalized: 82, confidence: 1 },
      { key: "independence", label: "Independence", normalized: 79, confidence: 0.8 },
      { key: "trust", label: "Trust", normalized: 55, confidence: 0.5 },
      { key: "vulnerability", label: "Vulnerability", normalized: 30, confidence: 0.3 },
    ]);
  });

  it("carries reflection questions and the recommendation snapshot straight through", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const recommendation = { assessmentSlug: "intimacy", assessmentName: "How Deep Do You Go?", bridgeCopy: "Curious what's next?" };
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation });
    expect(doc.reflectionQuestions).toEqual(generated.reflectionQuestions);
    expect(doc.recommendation).toEqual(recommendation);
  });

  it("allows a null recommendation (not every profile has an eligible next assessment)", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation: null });
    expect(doc.recommendation).toBeNull();
  });

  it("records full reproducibility metadata", async () => {
    const context = baseContext();
    const generated = await generateReport(context);
    const doc = assembleReportDocument({ context, generated, assessmentSlug: "love", recommendation: null });
    expect(doc.meta.assessmentSlug).toBe("love");
    expect(doc.meta.assessmentVersion).toBe(2);
    expect(doc.meta.reportEngineVersion).toBe(generated.reportEngineVersion);
    expect(doc.meta.promptVersion).toBe(generated.promptVersion);
    expect(doc.meta.personaVersion).toBe(generated.personaVersion);
    expect(doc.meta.modelVersion).toBe(generated.modelVersion);
    expect(new Date(doc.meta.generatedAt).toString()).not.toBe("Invalid Date");
  });
});
