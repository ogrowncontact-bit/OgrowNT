import type { AssessmentConfig, DimensionKey, DimensionState, ProfileDefinition, ProfileMatchingRule, ProfileResult } from "./types";

function inRange(score: number, range: [number, number]): boolean {
  return score >= range[0] && score <= range[1];
}

function scoreOf(scores: Record<DimensionKey, DimensionState>, dimKey: DimensionKey): number {
  return scores[dimKey]?.normalized ?? 50;
}

function satisfiesRequired(rule: ProfileMatchingRule, scores: Record<DimensionKey, DimensionState>): boolean {
  return Object.entries(rule.dimensionRanges).every(([dimKey, range]) => !range || inRange(scoreOf(scores, dimKey), range));
}

function violatesExclusion(rule: ProfileMatchingRule, scores: Record<DimensionKey, DimensionState>): boolean {
  return Object.entries(rule.excludeConditions ?? {}).some(([dimKey, range]) => !!range && inRange(scoreOf(scores, dimKey), range));
}

function optionalMatchCount(rule: ProfileMatchingRule, scores: Record<DimensionKey, DimensionState>): number {
  return Object.entries(rule.optionalConditions ?? {}).filter(([dimKey, range]) => !!range && inRange(scoreOf(scores, dimKey), range)).length;
}

/** Distance from a profile's required-range midpoints — used as a tiebreaker/fallback so every session lands on *some* primary profile even without an exact rule match. */
function distanceToProfile(profile: ProfileDefinition, scores: Record<DimensionKey, DimensionState>): number {
  const entries = Object.entries(profile.matchingRule.dimensionRanges);
  if (entries.length === 0) return Infinity;
  let total = 0;
  for (const [dimKey, range] of entries) {
    if (!range) continue;
    const midpoint = (range[0] + range[1]) / 2;
    total += Math.abs(scoreOf(scores, dimKey) - midpoint);
  }
  return total / entries.length;
}

export interface RankedProfile {
  profile: ProfileDefinition;
  satisfiesRequired: boolean;
  excluded: boolean;
  optionalMatches: number;
  distance: number;
}

/**
 * Ranks every profile — not just the ones that match — so a primary and
 * meaningfully-ordered secondary list both fall out of one pass. Order:
 * satisfies required (and not excluded) beats not; among those, more
 * satisfied optional conditions wins (distinguishes similar profiles);
 * then authored priority; then closeness to each profile's range
 * midpoints as a final, always-available tiebreak.
 */
export function rankProfiles(config: AssessmentConfig, scores: Record<DimensionKey, DimensionState>): RankedProfile[] {
  return config.profiles
    .map((profile) => {
      const excluded = violatesExclusion(profile.matchingRule, scores);
      const satisfies = !excluded && satisfiesRequired(profile.matchingRule, scores);
      return {
        profile,
        satisfiesRequired: satisfies,
        excluded,
        optionalMatches: optionalMatchCount(profile.matchingRule, scores),
        distance: distanceToProfile(profile, scores),
      };
    })
    .sort((a, b) => {
      if (a.satisfiesRequired !== b.satisfiesRequired) return a.satisfiesRequired ? -1 : 1;
      if (a.optionalMatches !== b.optionalMatches) return b.optionalMatches - a.optionalMatches;
      const priorityDiff = (b.profile.priority ?? 0) - (a.profile.priority ?? 0);
      if (priorityDiff !== 0) return priorityDiff;
      return a.distance - b.distance;
    });
}

/**
 * Deterministic profile matching — the arithmetic decides which profile(s)
 * fit; Profile AI (Phase 2) narrates this decision afterward, it does not
 * make it. See docs/ARCHITECTURE.md §6.
 */
export function matchProfiles(config: AssessmentConfig, scores: Record<DimensionKey, DimensionState>): ProfileResult {
  const ranked = rankProfiles(config, scores);
  const [primary, ...rest] = ranked;
  return {
    primary: primary.profile,
    secondary: rest.slice(0, 3).map((r) => r.profile),
  };
}

export interface ConditionExplanation {
  dimensionKey: DimensionKey;
  range: [number, number];
  score: number;
  satisfied: boolean;
}

export interface ProfileMatchExplanation {
  profileKey: string;
  isPrimary: boolean;
  required: ConditionExplanation[];
  optional: ConditionExplanation[];
  excluded: ConditionExplanation[];
  satisfiesRequired: boolean;
  isExcluded: boolean;
  optionalMatches: number;
}

function explainConditions(
  conditions: Partial<Record<DimensionKey, [number, number]>>,
  scores: Record<DimensionKey, DimensionState>
): ConditionExplanation[] {
  return Object.entries(conditions)
    .filter((entry): entry is [DimensionKey, [number, number]] => !!entry[1])
    .map(([dimensionKey, range]) => {
      const score = scoreOf(scores, dimensionKey);
      return { dimensionKey, range, score, satisfied: inRange(score, range) };
    });
}

/**
 * "Why did this person receive this profile?" — traces the primary
 * profile's decision back through every condition that was checked, not
 * just the ones that passed. Pairs with scoring.ts's explainDimension for
 * the full answers → signals → dimensions → conditions → profile chain.
 */
export function explainProfileMatch(config: AssessmentConfig, scores: Record<DimensionKey, DimensionState>): ProfileMatchExplanation[] {
  const ranked = rankProfiles(config, scores);
  const primaryKey = ranked[0]?.profile.key;

  return ranked.map((r) => ({
    profileKey: r.profile.key,
    isPrimary: r.profile.key === primaryKey,
    required: explainConditions(r.profile.matchingRule.dimensionRanges, scores),
    optional: explainConditions(r.profile.matchingRule.optionalConditions ?? {}, scores),
    excluded: explainConditions(r.profile.matchingRule.excludeConditions ?? {}, scores),
    satisfiesRequired: r.satisfiesRequired,
    isExcluded: r.excluded,
    optionalMatches: r.optionalMatches,
  }));
}
