import { allAssessments } from "@inner/content";
import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * Slug → live config registry, generated from @inner/content's full list.
 * Phase 5 (admin) replaces this static map with a published-version lookup
 * from `catalog.*`. Nothing outside this file should know how a config is
 * sourced — see docs/ARCHITECTURE.md §1.2.
 */
const registry: Record<string, AssessmentConfig> = Object.fromEntries(
  allAssessments.filter((a) => a.status === "published").map((a) => [a.slug, a])
);

export function getAssessmentConfig(slug: string): AssessmentConfig | null {
  return registry[slug] ?? null;
}

export function listPublishedSlugs(): string[] {
  return Object.keys(registry);
}
