import { loveAssessment } from "@inner/content";
import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * Slug → live config registry. Phase 1 ships one experience; Phase 4 grows
 * this to all 10, and Phase 5 (admin) replaces this static map with a
 * published-version lookup from `catalog.*`. Nothing outside this file
 * should know how a config is sourced — see docs/ARCHITECTURE.md §1.2.
 */
const registry: Record<string, AssessmentConfig> = {
  [loveAssessment.slug]: loveAssessment,
};

export function getAssessmentConfig(slug: string): AssessmentConfig | null {
  return registry[slug] ?? null;
}

export function listPublishedSlugs(): string[] {
  return Object.keys(registry);
}
