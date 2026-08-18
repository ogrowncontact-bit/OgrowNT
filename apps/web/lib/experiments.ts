import { createHash } from "node:crypto";

/**
 * A/B testing foundation — deliberately just the architecture, per the
 * spec's own scope: "do not implement dozens of experiments." No live
 * experiment is configured below; add an entry to EXPERIMENTS and start
 * tracking exposures (see trackExperimentExposure in lib/analytics.ts
 * usage below) when there's a specific test to run. Changing what paying
 * customers actually see is a product decision, not something to invent
 * unprompted — this file only makes running one, when asked, a few lines
 * of work instead of a new subsystem.
 */

export interface ExperimentDefinition {
  id: string;
  variants: string[];
}

export const EXPERIMENTS: ExperimentDefinition[] = [];

export function getActiveExperiment(id: string): ExperimentDefinition | undefined {
  return EXPERIMENTS.find((e) => e.id === id);
}

/**
 * Deterministic and stable per (experimentId, anonymousSessionId) — the
 * same visitor always lands in the same variant, computed from a hash
 * rather than stored, so assignment needs no DB write and survives a
 * server restart without drifting.
 */
export function assignVariant(experimentId: string, anonymousSessionId: string, variants: string[]): string {
  if (variants.length === 0) throw new Error(`Experiment "${experimentId}" has no variants configured`);
  const hash = createHash("sha256").update(`${experimentId}:${anonymousSessionId}`).digest();
  return variants[hash[0] % variants.length];
}
