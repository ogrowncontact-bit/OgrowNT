export type ConfidenceBucket = "high" | "medium" | "low";

/**
 * Turns a raw 0..1 confidence into a coarse bucket used to calibrate prompt
 * language (§UNCERTAINTY — "every major interpretation should have a
 * confidence level"). Buckets, not the raw number, are what's safe to lean
 * on for language strength: a model told "0.42" has no shared sense of what
 * that means, but "medium confidence, hedge accordingly" is directly
 * actionable. Never surfaced to the end user as a number either way.
 */
export function bucketConfidence(confidence: number): ConfidenceBucket {
  if (confidence >= 0.66) return "high";
  if (confidence >= 0.33) return "medium";
  return "low";
}
