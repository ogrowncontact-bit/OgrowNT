/**
 * INNER is explicitly not a diagnostic platform (product spec, "IMPORTANT AI
 * PRINCIPLE"). This is the deterministic check every piece of AI-generated,
 * user-facing copy must pass before it's stored or shown — we don't trust
 * the system prompt alone to enforce this. See docs/ARCHITECTURE.md §4.1.
 *
 * Two tiers:
 *  - REWRITABLE openers ("You are...", "You have...") get auto-hedged.
 *  - HARD-BANNED clinical/diagnostic vocabulary has no safe auto-rewrite —
 *    any match means the caller must fall back to static template copy.
 */

const REWRITABLE_OPENERS: { pattern: RegExp; replacement: string }[] = [
  { pattern: /\byou are\b/gi, replacement: "your responses suggest you tend to be" },
  { pattern: /\byou're\b/gi, replacement: "your responses suggest you tend to be" },
  { pattern: /\byou have\b/gi, replacement: "your responses suggest you have" },
  { pattern: /\byou've\b/gi, replacement: "your responses suggest you've" },
  { pattern: /\byou suffer from\b/gi, replacement: "your responses may point to challenges with" },
];

const HARD_BANNED_TERMS: RegExp[] = [
  /\bdisorders?\b/i,
  /\bsyndromes?\b/i,
  /\bdiagnos(is|e|ed|ing|es)\b/i,
  /\bpatholog(y|ical|ies)\b/i,
  /\bdysfunctions?(al)?\b/i,
  /\bmental illness(es)?\b/i,
  /\bpersonality disorders?\b/i,
  /\bclinical(ly)?\b/i,
  /\bnarcissis(t|tic|m)\b/i,
  /\bcodependen(t|cy)\b/i,
  /\btrauma(tized|tic)?\b/i,
  /\bpsychopath(ic)?\b/i,
  /\bsociopath(ic)?\b/i,
];

export function sanitizeOpeners(text: string): string {
  let out = text;
  for (const { pattern, replacement } of REWRITABLE_OPENERS) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

export function findHardBannedTerms(text: string): string[] {
  return HARD_BANNED_TERMS.filter((pattern) => pattern.test(text)).map((pattern) => pattern.source);
}

export interface NonDiagnosticCheck {
  ok: boolean;
  text: string;
  violations: string[];
}

/** Sanitizes rewritable openers, then rejects outright if hard-banned vocabulary remains. */
export function enforceNonDiagnostic(text: string): NonDiagnosticCheck {
  const sanitized = sanitizeOpeners(text);
  const violations = findHardBannedTerms(sanitized);
  return { ok: violations.length === 0, text: sanitized, violations };
}
