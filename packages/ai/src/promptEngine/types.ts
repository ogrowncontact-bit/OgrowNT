/** Layer 5 "TONE CONFIGURATION" — each 0..1, purely descriptive parameters the PromptEngine turns into instruction phrasing. Never sent to the model as raw numbers. */
export interface ToneConfig {
  /** How emotionally warm vs. clinically neutral the voice should read. */
  warmth: number;
  /** How plainly vs. gently the voice names a pattern. */
  directness: number;
  /** How much the voice elaborates/connects ideas vs. stays brief. */
  depth: number;
  /** How casual vs. formal the register is. */
  formality: number;
}

/**
 * Layer 2 "ASSESSMENT PERSONA" — the specific assessment's expert
 * perspective. Sourced from a published `PromptTemplate` DB row (see
 * apps/web/lib/promptTemplates.ts); packages/ai has no persistence of its
 * own, so this is always passed in as plain data, never fetched here.
 */
export interface AssessmentPersona {
  assessmentSlug: string;
  name: string;
  focus: string;
  /** The persona's own voice/perspective instructions — admin-editable, versioned. */
  prompt: string;
  tone: ToneConfig;
  version: number;
}

/** Layer 3 "ASSESSMENT FRAMEWORK" — reused directly from the assessment's own config, never duplicated content. */
export interface FrameworkLayer {
  dimensionLabels: string[];
  /** Human-readable tension-pair labels this assessment can detect, if any — gives the model a sense of what kinds of dimension interactions are meaningful here specifically. */
  tensionLabels: string[];
}

export interface PromptEngineInput {
  assessmentId: string; // slug
  assessmentVersion: number;
  language: string;
  reportType: "individual" | "deep" | "enrichment" | "response";
  persona: AssessmentPersona;
  framework: FrameworkLayer;
  /** Layer 5 "REPORT OBJECTIVE" — what this specific section/call must accomplish. Omit for calls that aren't section-scoped. */
  sectionObjective?: string;
  /**
   * Appended verbatim after the composed persona+framework layers —
   * module-specific operational instructions (exact hedging phrases, banned
   * terms, output shape/length rules) that stay with the calling module
   * (reportAI, profileEnrichmentAI, ...) rather than living in the reusable
   * Global or Persona layers, since they're about *how* to answer, not
   * *who* is answering.
   */
  moduleInstructions: string;
}

export interface CompiledPrompt {
  system: string;
  /** Echoed back so the caller can record which persona version actually narrated a given generation (Report.personaVersion). */
  personaVersion: number;
}
