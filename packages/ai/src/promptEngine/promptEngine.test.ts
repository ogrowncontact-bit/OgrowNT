import { describe, expect, it } from "vitest";
import { compilePrompt } from "./promptEngine";
import { GLOBAL_INNER_VOICE } from "./globalPersona";
import { DEFAULT_ASSESSMENT_PERSONAS } from "./personas";
import { sectionObjectiveFor } from "./sectionObjectives";
import type { AssessmentPersona, PromptEngineInput } from "./types";

const persona: AssessmentPersona = {
  assessmentSlug: "love",
  name: "The Relationship Observer",
  focus: "connection, trust, independence, vulnerability, and emotional patterns",
  prompt: "You notice the quiet negotiation between wanting someone close and staying yourself.",
  tone: { warmth: 0.8, directness: 0.4, depth: 0.7, formality: 0.25 },
  version: 3,
};

function baseInput(overrides: Partial<PromptEngineInput> = {}): PromptEngineInput {
  return {
    assessmentId: "love",
    assessmentVersion: 1,
    language: "en",
    reportType: "individual",
    persona,
    framework: { dimensionLabels: ["Connection", "Independence"], tensionLabels: ["wanting closeness and independence"] },
    moduleInstructions: "Write 2-4 sentences per section.",
    ...overrides,
  };
}

describe("compilePrompt", () => {
  it("composes all layers into one system prompt: global, persona, framework, module instructions", () => {
    const compiled = compilePrompt(baseInput());
    expect(compiled.system).toContain(GLOBAL_INNER_VOICE.split("\n")[0]); // Layer 1 present verbatim
    expect(compiled.system).toContain(persona.name);
    expect(compiled.system).toContain(persona.prompt);
    expect(compiled.system).toContain("Connection");
    expect(compiled.system).toContain("Independence");
    expect(compiled.system).toContain("wanting closeness and independence");
    expect(compiled.system).toContain("Write 2-4 sentences per section.");
  });

  it("echoes back the persona's version for reproducibility tracking", () => {
    const compiled = compilePrompt(baseInput());
    expect(compiled.personaVersion).toBe(3);
  });

  it("includes a section objective when one is given", () => {
    const compiled = compilePrompt(baseInput({ sectionObjective: "Explain the dominant pattern." }));
    expect(compiled.system).toContain("Explain the dominant pattern.");
  });

  it("omits the section-objective line entirely when none is given", () => {
    const compiled = compilePrompt(baseInput());
    expect(compiled.system).not.toContain("For this section specifically:");
  });

  it("adds an explicit native-language instruction for a non-English language, and none for English", () => {
    const en = compilePrompt(baseInput({ language: "en" }));
    const es = compilePrompt(baseInput({ language: "es" }));
    expect(en.system.toLowerCase()).not.toContain("write your entire response naturally in spanish");
    expect(es.system.toLowerCase()).toContain("write your entire response naturally in spanish");
  });

  it("falls back to English for an unsupported language rather than erroring", () => {
    const compiled = compilePrompt(baseInput({ language: "de" }));
    expect(compiled.system.toLowerCase()).not.toContain("write your entire response naturally in german");
  });

  it("turns tone parameters into instruction phrasing, never raw numbers", () => {
    const compiled = compilePrompt(baseInput());
    expect(compiled.system).not.toMatch(/warmth[:\s]*0\.\d/i);
    expect(compiled.system.toLowerCase()).toContain("warm");
  });

  it("omits the framework line entirely when an assessment has no tension pairs", () => {
    const compiled = compilePrompt(baseInput({ framework: { dimensionLabels: ["Connection"], tensionLabels: [] } }));
    expect(compiled.system).not.toContain("Dimension interactions worth noticing here specifically");
  });
});

describe("DEFAULT_ASSESSMENT_PERSONAS", () => {
  const expectedSlugs = [
    "love",
    "relationship",
    "jealousy",
    "intimacy",
    "vulnerability",
    "connection",
    "social",
    "communication",
    "hidden-self",
    "decision",
  ];

  it("defines exactly one default persona per assessment, matching every published assessment slug", () => {
    const slugs = DEFAULT_ASSESSMENT_PERSONAS.map((p) => p.assessmentSlug).sort();
    expect(slugs).toEqual([...expectedSlugs].sort());
  });

  it("every persona has non-empty name/focus/prompt and tone values within 0..1", () => {
    for (const p of DEFAULT_ASSESSMENT_PERSONAS) {
      expect(p.name.length).toBeGreaterThan(0);
      expect(p.focus.length).toBeGreaterThan(0);
      expect(p.prompt.length).toBeGreaterThan(0);
      for (const value of Object.values(p.tone)) {
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(1);
      }
    }
  });

  it("the jealousy persona explicitly instructs the model never to shame the user, per spec", () => {
    const jealousy = DEFAULT_ASSESSMENT_PERSONAS.find((p) => p.assessmentSlug === "jealousy")!;
    expect(jealousy.prompt.toLowerCase()).toContain("never shame");
  });

  it("the hidden-self persona never claims to reveal the subconscious", () => {
    const hiddenSelf = DEFAULT_ASSESSMENT_PERSONAS.find((p) => p.assessmentSlug === "hidden-self")!;
    expect(hiddenSelf.prompt.toLowerCase()).not.toContain("subconscious mind");
    expect(hiddenSelf.prompt.toLowerCase()).toContain("never claim to reveal the subconscious");
  });
});

describe("sectionObjectiveFor", () => {
  it("returns a specific role and objective for well-known section keys", () => {
    expect(sectionObjectiveFor("inner_tension", "The Tension Inside Your Profile").role).toBe("tension");
    expect(sectionObjectiveFor("strengths", "Your Strengths").role).toBe("strengths");
    expect(sectionObjectiveFor("reflection", "Your Personal Reflection").role).toBe("reflection");
  });

  it("falls back to a generic narrative objective for an admin-authored custom key, never an empty one", () => {
    const result = sectionObjectiveFor("some_custom_admin_key", "A Custom Section");
    expect(result.role).toBe("narrative");
    expect(result.objective.length).toBeGreaterThan(0);
    expect(result.objective).toContain("A Custom Section");
  });
});
