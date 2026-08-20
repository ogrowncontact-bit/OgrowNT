import { prisma } from "@inner/db";
import { DEFAULT_ASSESSMENT_PERSONAS, type AssessmentPersona } from "@inner/ai";

/**
 * Reads the currently-published PromptTemplate (Layer 2 "Assessment
 * Persona") for an assessment. Falls back to the code-level default persona
 * (packages/ai's DEFAULT_ASSESSMENT_PERSONAS) when nothing has been
 * published yet — a fresh install, or a slug not seeded — so report
 * generation never blocks on an admin having opened the prompt editor.
 * packages/ai stays free of any DB dependency; this is the one place that
 * turns a DB row into the plain-data shape the PromptEngine consumes.
 */
export async function getPublishedPersona(assessmentSlug: string): Promise<AssessmentPersona> {
  const row = await prisma.promptTemplate.findFirst({
    where: { assessmentSlug, status: "published" },
    orderBy: { version: "desc" },
  });
  if (row) {
    return {
      assessmentSlug: row.assessmentSlug,
      name: row.personaName,
      focus: row.personaFocus,
      prompt: row.personaPrompt,
      tone: { warmth: row.toneWarmth, directness: row.toneDirectness, depth: row.toneDepth, formality: row.toneFormality },
      version: row.version,
    };
  }

  const fallback = DEFAULT_ASSESSMENT_PERSONAS.find((p) => p.assessmentSlug === assessmentSlug);
  if (fallback) {
    return { assessmentSlug, name: fallback.name, focus: fallback.focus, prompt: fallback.prompt, tone: fallback.tone, version: 0 };
  }

  // Genuinely unknown assessment (a brand-new admin-created experience with no
  // authored persona yet) — a neutral generic persona, never a hard failure.
  return {
    assessmentSlug,
    name: "The INNER Observer",
    focus: "the patterns in this assessment's own dimensions",
    prompt: "You narrate this assessment's results the same way you would any other INNER experience — grounded, specific, and warm.",
    tone: { warmth: 0.6, directness: 0.5, depth: 0.6, formality: 0.4 },
    version: 0,
  };
}
