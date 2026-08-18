import { describe, expect, it } from "vitest";
import { validateReportQuality } from "./reportQualityValidator";
import type { GeneratedReportSection } from "./reportAI";

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
