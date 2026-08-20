import { describe, expect, it } from "vitest";
import { validateReportQuality, validateReportDocument } from "./reportQualityValidator";
import type { GeneratedReportSection } from "./reportAI";
import type { ReportDocument } from "./reportDocument";

function section(key: string, body: string): GeneratedReportSection {
  return { key, title: key, body, aiGenerated: true };
}

const baseParams = {
  expectedSectionKeys: ["signature", "strengths"],
  dimensionLabels: ["Connection", "Independence"],
  primaryProfileName: "The Independent Connector",
  language: "en",
};

describe("validateReportQuality — structural checks", () => {
  it("passes a complete, personalized, non-diagnostic report", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [
        section("signature", "Your responses suggest a strong pull toward Connection, balanced by real Independence."),
        section("strengths", "Your responses suggest real strength in how you protect your own Independence."),
      ],
    });
    expect(result.ok).toBe(true);
    expect(result.issues).toEqual([]);
  });

  it("flags a missing section as a hard failure", () => {
    const result = validateReportQuality({ ...baseParams, sections: [section("signature", "Some text about Connection.")] });
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "missing_section" && i.sectionKey === "strengths")).toBe(true);
  });

  it("flags an empty section as a hard failure", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [section("signature", "Text about Connection."), section("strengths", "   ")],
    });
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "empty_section" && i.sectionKey === "strengths")).toBe(true);
  });

  it("flags a banned diagnostic term as a hard failure", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [
        section("signature", "Your responses suggest a pattern related to Connection."),
        section("strengths", "This could indicate a personality disorder in some cases."),
      ],
    });
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "banned_term")).toBe(true);
  });
});

describe("validateReportQuality — soft signals (recorded, not hard-fail)", () => {
  it("flags an absolute claim without failing the whole report", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [
        section("signature", "Your responses suggest a pattern related to Connection."),
        section("strengths", "You will always need Independence and this never changes."),
      ],
    });
    expect(result.issues.some((i) => i.type === "absolute_claim")).toBe(true);
    expect(result.ok).toBe(true); // absolute_claim alone doesn't hard-fail — it gets swapped per-section by the caller
  });

  it("flags near-duplicate sections as repetitive", () => {
    const body = "Your responses suggest a strong pull toward Connection and a real need for Independence in how you relate.";
    const result = validateReportQuality({ ...baseParams, sections: [section("signature", body), section("strengths", body)] });
    expect(result.issues.some((i) => i.type === "repetitive")).toBe(true);
  });

  it("flags a report that never mentions the actual scored dimensions as generic", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [
        section("signature", "Your responses suggest a meaningful pattern worth reflecting on."),
        section("strengths", "Your responses point to real strength in how you show up for people."),
      ],
    });
    expect(result.issues.some((i) => i.type === "not_personalized")).toBe(true);
  });

  it("does not flag personalization when the report references the scored dimensions by name", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [
        section("signature", "Your Connection score shapes how you show up early on."),
        section("strengths", "Your Independence stands out as a real strength in your answers."),
      ],
    });
    expect(result.issues.some((i) => i.type === "not_personalized")).toBe(false);
  });

  it("flags a language mismatch when Spanish is requested but the report reads as English", () => {
    const result = validateReportQuality({
      ...baseParams,
      language: "es",
      sections: [
        section("signature", "Your responses suggest a pattern related to Connection and the way you show up."),
        section("strengths", "Your responses suggest real strength in Independence."),
      ],
    });
    expect(result.issues.some((i) => i.type === "language_mismatch")).toBe(true);
  });

  it("does not flag a genuinely Spanish report", () => {
    const result = validateReportQuality({
      ...baseParams,
      language: "es",
      sections: [
        section("signature", "Tus respuestas sugieren un patrón relacionado con la Conexión que muestras con las personas."),
        section("strengths", "Tus respuestas sugieren una fortaleza real en tu Independencia y en cómo te cuidas."),
      ],
    });
    expect(result.issues.some((i) => i.type === "language_mismatch")).toBe(false);
  });
});

describe("validateReportQuality — word count", () => {
  it("reports a word count across all sections", () => {
    const result = validateReportQuality({
      ...baseParams,
      sections: [section("signature", "one two three"), section("strengths", "four five")],
    });
    expect(result.wordCount).toBe(5);
  });
});

function baseDocument(overrides: Partial<ReportDocument> = {}): ReportDocument {
  return {
    meta: {
      assessmentName: "How Do You Love?",
      assessmentSlug: "love",
      assessmentVersion: 1,
      reportEngineVersion: 1,
      promptVersion: 3,
      personaVersion: 1,
      modelVersion: "claude-sonnet-5",
      language: "en",
      generatedAt: new Date().toISOString(),
    },
    profile: { name: "The Independent Connector", description: "Values closeness while protecting independence.", secondaryNames: [] },
    summary: "Your responses point toward a strong pull between connection and independence.",
    dimensions: [{ key: "connection", label: "Connection", normalized: 80, confidence: 0.8 }],
    sections: [{ key: "signature", title: "Your INNER Signature", body: "Some real, specific text.", aiGenerated: true, role: "signature" }],
    reflectionQuestions: ["When do you notice this pattern?"],
    recommendation: { assessmentSlug: "intimacy", assessmentName: "How Deep Do You Go?", bridgeCopy: "Curious what's next?" },
    ...overrides,
  };
}

const VALID_PDF = Buffer.concat([Buffer.from("%PDF-1.7\n"), Buffer.alloc(2000, 0x20)]);

describe("validateReportDocument", () => {
  it("passes a complete document with a valid PDF", () => {
    const result = validateReportDocument(baseDocument(), VALID_PDF);
    expect(result.ok).toBe(true);
    expect(result.issues).toEqual([]);
  });

  it("flags a missing profile name/description as a hard failure", () => {
    const result = validateReportDocument(baseDocument({ profile: { name: "", description: "", secondaryNames: [] } }));
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "missing_profile")).toBe(true);
  });

  it("flags a missing summary as a hard failure", () => {
    const result = validateReportDocument(baseDocument({ summary: "   " }));
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "missing_summary")).toBe(true);
  });

  it("flags zero sections as a hard failure", () => {
    const result = validateReportDocument(baseDocument({ sections: [] }));
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "missing_sections")).toBe(true);
  });

  it("flags placeholder text anywhere in the document as a hard failure", () => {
    const result = validateReportDocument(
      baseDocument({ sections: [{ key: "signature", title: "x", body: "Lorem ipsum dolor sit amet.", aiGenerated: false, role: "signature" }] })
    );
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "placeholder_text")).toBe(true);
  });

  it("flags a PDF that doesn't start with the %PDF- magic bytes as a hard failure", () => {
    const result = validateReportDocument(baseDocument(), Buffer.from("not a real pdf"));
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "pdf_invalid")).toBe(true);
  });

  it("flags an empty PDF buffer as a hard failure", () => {
    const result = validateReportDocument(baseDocument(), Buffer.alloc(0));
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.type === "pdf_missing")).toBe(true);
  });

  it("doesn't check the PDF at all when none is given (e.g. web-only validation before rendering)", () => {
    const result = validateReportDocument(baseDocument());
    expect(result.ok).toBe(true);
  });

  it("records a missing recommendation but never treats it as a hard failure — not every profile has an eligible next assessment", () => {
    const result = validateReportDocument(baseDocument({ recommendation: null }), VALID_PDF);
    expect(result.ok).toBe(true);
    expect(result.issues.some((i) => i.type === "recommendation_missing")).toBe(true);
  });
});
