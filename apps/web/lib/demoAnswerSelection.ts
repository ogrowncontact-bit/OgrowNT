import type { Question, SessionState } from "@inner/assessment-engine";
import { openTextAnswerFor, type DemoPersona } from "./demoPersonas";

export interface DemoAnswer {
  selectedOptionKeys?: string[];
  scaleValue?: number;
  openText?: string;
}

/**
 * Picks the real option (or scale value, or persona-flavored open text) that
 * best matches a demo persona's target dimension directions — never a
 * fabricated answer, always one of the question's own authored options.
 *
 * A dimension with no target direction is treated as "stay balanced": among
 * ties on the targeted score, the option that pulls that dimension's
 * *current running* normalized score (from `state`, starts at 50) back
 * toward the middle wins. This is what makes Persona D (no targets at all)
 * settle into a genuinely balanced read across the whole session, rather
 * than drifting wherever LOVE's option authoring happens to lean.
 */
export function chooseAnswerForPersona(question: Question, persona: DemoPersona, state: SessionState): DemoAnswer {
  if (question.type === "open_text") {
    return { openText: openTextAnswerFor(persona, question.key) };
  }

  if (question.type === "scale") {
    const max = question.scaleMax ?? 5;
    const direction = question.scaleDimension ? persona.targetDirections[question.scaleDimension] : undefined;
    if (direction === "high") return { scaleValue: max };
    if (direction === "low") return { scaleValue: 1 };
    return { scaleValue: Math.ceil(max / 2) };
  }

  // single_select / multi_select
  const options = question.options ?? [];
  let best = options[0];
  let bestTargetedScore = -Infinity;
  let bestBalanceScore = -Infinity;

  for (const option of options) {
    let targetedScore = 0;
    let balanceScore = 0;
    for (const [dimensionKey, contribution] of Object.entries(option.dimensionContributions)) {
      const value = contribution ?? 0;
      const direction = persona.targetDirections[dimensionKey];
      if (direction === "high") targetedScore += value;
      else if (direction === "low") targetedScore -= value;
      else {
        // Not one of this persona's targets — reward whichever sign nudges
        // this dimension's current running score back toward 50.
        const current = state.dimensionScores[dimensionKey]?.normalized ?? 50;
        balanceScore += current >= 50 ? -value : value;
      }
    }

    if (targetedScore > bestTargetedScore || (targetedScore === bestTargetedScore && balanceScore > bestBalanceScore)) {
      best = option;
      bestTargetedScore = targetedScore;
      bestBalanceScore = balanceScore;
    }
  }

  return best ? { selectedOptionKeys: [best.key] } : {};
}
