import type { AssessmentConfig, DimensionKey, DimensionState, ProfileDefinition, ProfileResult } from "./types";

function matchesRanges(profile: ProfileDefinition, scores: Record<DimensionKey, DimensionState>): boolean {
  return Object.entries(profile.matchingRule.dimensionRanges).every(([dimKey, range]) => {
    if (!range) return true;
    const score = scores[dimKey]?.normalized ?? 50;
    return score >= range[0] && score <= range[1];
  });
}

/** Distance from a profile's range midpoints — used as a tiebreaker/fallback so every session lands on *some* primary profile even without an exact rule match. */
function distanceToProfile(profile: ProfileDefinition, scores: Record<DimensionKey, DimensionState>): number {
  const entries = Object.entries(profile.matchingRule.dimensionRanges);
  if (entries.length === 0) return Infinity;
  let total = 0;
  for (const [dimKey, range] of entries) {
    if (!range) continue;
    const score = scores[dimKey]?.normalized ?? 50;
    const midpoint = (range[0] + range[1]) / 2;
    total += Math.abs(score - midpoint);
  }
  return total / entries.length;
}

/**
 * Deterministic profile matching — the arithmetic decides which profile(s)
 * fit; Profile AI (Phase 2) narrates this decision afterward, it does not
 * make it. See docs/ARCHITECTURE.md §6.
 */
export function matchProfiles(config: AssessmentConfig, scores: Record<DimensionKey, DimensionState>): ProfileResult {
  const exactMatches = config.profiles.filter((p) => matchesRanges(p, scores));

  const ranked =
    exactMatches.length > 0
      ? exactMatches
      : [...config.profiles].sort((a, b) => distanceToProfile(a, scores) - distanceToProfile(b, scores));

  const [primary, ...rest] = ranked;
  return {
    primary,
    secondary: rest.slice(0, 3),
  };
}
