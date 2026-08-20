import { GLOBAL_INNER_VOICE } from "./globalPersona";
import { toneVoiceInstruction } from "./toneVoice";
import { resolvedLanguage, languageInstruction } from "./language";
import type { CompiledPrompt, PromptEngineInput } from "./types";

/**
 * Composes the five prompt layers (docs/ARCHITECTURE.md's Prompt
 * Orchestration System) into one system prompt:
 *   1. Global INNER voice (code-only, never admin-editable)
 *   2. Assessment persona (admin-editable, versioned — see PromptTemplate)
 *   3. Assessment framework (this assessment's own dimensions/tensions)
 *   4. Evidence — deliberately NOT composed here; each calling module
 *      (reportAI, profileEnrichmentAI, ...) already builds its own
 *      evidence block from its own structured input shape, and duplicating
 *      that formatting logic here would just be a second implementation of
 *      the same thing. The PromptEngine owns "who is answering and what
 *      they're allowed to say", not "how the evidence is formatted" — the
 *      caller appends its own evidence block to the userMessage.
 *   5. Section objective (what this specific call must accomplish)
 * Pure and synchronous — no AI call, no DB read, no side effects. Callers
 * fetch the persona (apps/web/lib/promptTemplates.ts) and framework data
 * themselves and pass them in as plain data, keeping packages/ai free of
 * any persistence dependency.
 */
export function compilePrompt(input: PromptEngineInput): CompiledPrompt {
  const language = resolvedLanguage(input.language);
  const parts: string[] = [GLOBAL_INNER_VOICE];

  parts.push(
    `You are narrating "${input.assessmentId}" as ${input.persona.name} — ${input.persona.focus}. ${input.persona.prompt}`
  );
  parts.push(toneVoiceInstruction(input.persona.tone));

  if (input.framework.dimensionLabels.length > 0) {
    parts.push(`This assessment measures: ${input.framework.dimensionLabels.join(", ")}.`);
  }
  if (input.framework.tensionLabels.length > 0) {
    parts.push(`Dimension interactions worth noticing here specifically include: ${input.framework.tensionLabels.join("; ")}.`);
  }

  if (input.sectionObjective) {
    parts.push(`For this section specifically: ${input.sectionObjective}`);
  }

  parts.push(input.moduleInstructions);

  const langInstruction = languageInstruction(language);
  if (langInstruction) parts.push(langInstruction.trim());

  return { system: parts.join("\n\n"), personaVersion: input.persona.version };
}
