/**
 * Crisis-language safety net (docs/ARCHITECTURE.md §4.1, §12). This is
 * deterministic and runs before any AI call — INNER is not equipped to
 * handle a genuine crisis disclosure, so detection can't depend on a model
 * being reachable or interpreting things "helpfully." A false positive just
 * shows a calm, optional message; a false negative is the real cost, so
 * these patterns lean broad on purpose.
 *
 * No country-specific hotline number is included — those go stale and vary
 * by region, and a wrong one is worse than a generic prompt to reach out to
 * someone trusted or a local service.
 */
const CONCERN_PATTERNS: RegExp[] = [
  /\b(kill|end)(ing)?\s+(myself|my life)\b/i,
  /\bsuicid(e|al)\b/i,
  /\bself[-\s]?harm(ing)?\b/i,
  /\b(want|wanted|wish(ed)?)\s+to\s+(die|disappear forever|not exist|not be alive)\b/i,
  /\bdon'?t\s+want\s+to\s+(live|be alive|exist anymore)\b/i,
  /\b(he|she|they|my (partner|ex|boyfriend|girlfriend|husband|wife))\s+(hits?|hit|beats?|beat|abuses?|abused|threatens?|threatened)\s+me\b/i,
  /\bI'?m\s+being\s+abused\b/i,
  /\bafraid (he|she|they) (will|might|is going to) hurt me\b/i,
];

export const SUPPORT_MESSAGE =
  "What you shared matters, and it sounded like it might be a heavy moment. If things feel difficult right now, consider reaching out to someone you trust or a local support service — you don't have to carry it alone. Whenever you're ready, we'll continue.";

export function detectSafetyConcern(text: string): boolean {
  return CONCERN_PATTERNS.some((pattern) => pattern.test(text));
}
