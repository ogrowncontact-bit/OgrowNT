/**
 * FASE 29 §FREE RESULT — a single deterministic reflection question for the
 * free result screen, grounded in the session's own top dimension and (if
 * present) its strongest tension. Deliberately not an AI call: the premium
 * report already has its own richer, AI-capable reflection questions
 * (packages/ai/src/reportAI.ts) — this is a lighter, free-tier touch that
 * doesn't answer anything, just like the premium ones are required not to.
 */
export function buildFreeReflectionQuestion(topDimensionLabel: string, tensionLabel?: string): string {
  if (tensionLabel) {
    return `Where in your life does ${tensionLabel} show up most clearly?`;
  }
  return `When has ${topDimensionLabel.toLowerCase()} served you well — and when has it gotten in your way?`;
}
