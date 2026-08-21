export type DimensionDirection = "high" | "low";

/**
 * Minimal shape lib/demoAnswerSelection.ts's chooseAnswerForPersona actually
 * needs — DemoPersona (below) satisfies it, and so does the FASE 31 QA
 * simulation's lighter QaPersona (lib/qa/loveQaPersonas.ts), which has no
 * label/summary/flavored open text of its own.
 */
export interface AnswerSelectionPersona {
  targetDirections: Partial<Record<string, DimensionDirection>>;
  openTextAnswers?: Record<string, string>;
}

export interface DemoPersona extends AnswerSelectionPersona {
  key: string;
  label: string;
  /** Shown next to the persona in the admin picker — describes the pattern, never claims a specific profile name (the real matcher decides that). */
  summary: string;
  /** Persona-flavored answers for LOVE's two core open_text questions — the assessment's own real AI interpretation still runs on this text, same as a genuine answer. */
  openTextAnswers: Record<string, string>;
}

const DEFAULT_OPEN_TEXT =
  "I noticed myself thinking it through more than usual before I said anything to them.";

/**
 * FASE 29 §DEMO PERSONAS — 5 named patterns for LOVE specifically, driving
 * apps/web/lib/demoAnswerSelection.ts's real-option selection so an admin
 * can walk the actual engine end to end and see the report genuinely change.
 * Not a new data model — a static config, matching the mega-spec's "stop
 * adding major new functionality" instruction.
 */
export const LOVE_DEMO_PERSONAS: DemoPersona[] = [
  {
    key: "a_high_connection_high_vulnerability",
    label: "Persona A — High Connection, High Vulnerability",
    summary: "Leans in early, trusts readily, and lets people see the real version of them once they're in.",
    targetDirections: {
      connection: "high",
      vulnerability: "high",
      trust: "high",
      emotional_openness: "high",
      independence: "low",
    },
    openTextAnswers: {
      closeness_dependency:
        "Honestly I can't think of a time I held back once I decided I trusted someone — if anything I probably lean in too fast.",
      uncertainty_response:
        "I usually just tell them directly that I'm feeling uncertain instead of sitting with it alone.",
    },
  },
  {
    key: "b_high_independence_moderate_connection",
    label: "Persona B — High Independence, Moderate Connection",
    summary: "Protects personal space first and lets closeness happen on their own timeline, not by default.",
    targetDirections: {
      independence: "high",
      vulnerability: "low",
      distance_response: "low",
    },
    openTextAnswers: {
      closeness_dependency:
        "There was a moment I wanted to say more, but I decided it was better to keep some of it to myself for now.",
      uncertainty_response:
        "I usually just keep going with my own routine and let it settle on its own rather than chasing an answer.",
    },
  },
  {
    key: "c_low_trust_high_reassurance",
    label: "Persona C — Low Trust, High Reassurance-Seeking",
    summary: "Wants closeness but doesn't extend trust easily, and leans on consistent reassurance to feel secure.",
    targetDirections: {
      trust: "low",
      validation: "high",
      connection: "high",
      security: "low",
    },
    openTextAnswers: {
      closeness_dependency:
        "I wanted to get closer but I held back until I was sure they actually meant what they said.",
      uncertainty_response:
        "I usually look for some sign that things are still okay — a text back, anything — before I can relax about it.",
    },
  },
  {
    key: "d_balanced",
    label: "Persona D — Balanced Dimensions",
    summary: "No strong lean in either direction — connection and independence, openness and caution, stay fairly even.",
    targetDirections: {},
    openTextAnswers: {
      closeness_dependency:
        "It depends a lot on the situation — sometimes I lean in, sometimes I hold back, it's not really a fixed pattern for me.",
      uncertainty_response:
        "I usually just wait and see how it plays out rather than reacting right away either way.",
    },
  },
  {
    key: "e_mixed_tension",
    label: "Persona E — Mixed Profile (Connection + Independence Tension)",
    summary: "Wants real closeness and strongly protects independence at the same time — a genuine, coexisting tension.",
    targetDirections: {
      connection: "high",
      independence: "high",
      affection_expression: "high",
    },
    openTextAnswers: {
      closeness_dependency:
        "I wanted to get closer, but I also didn't want to lose the parts of my life that are just mine, so I pulled back a little.",
      uncertainty_response:
        "Part of me wants to reach out and part of me wants to give it space — I usually end up doing a bit of both.",
    },
  },
];

export function getDemoPersona(key: string): DemoPersona | undefined {
  return LOVE_DEMO_PERSONAS.find((p) => p.key === key);
}

export function openTextAnswerFor(persona: AnswerSelectionPersona, questionKey: string): string {
  return persona.openTextAnswers?.[questionKey] ?? DEFAULT_OPEN_TEXT;
}
