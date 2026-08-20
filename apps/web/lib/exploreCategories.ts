/**
 * Presentation-only grouping for /explore (FASE 23 §EXPLORE PAGE) — the 10
 * real assessments' own `category` field ("relationships" | "self") is
 * coarser and used elsewhere (e.g. the admin assessment list), so this maps
 * the same real slugs to the spec's finer 5-category taxonomy without
 * touching that field or anything that reads it.
 */
export const EXPLORE_CATEGORIES = ["Relationships", "Connection", "Communication", "Self Discovery", "Decision"] as const;
export type ExploreCategory = (typeof EXPLORE_CATEGORIES)[number];

const SLUG_TO_CATEGORY: Record<string, ExploreCategory> = {
  love: "Relationships",
  relationship: "Relationships",
  jealousy: "Relationships",
  intimacy: "Relationships",
  vulnerability: "Connection",
  connection: "Connection",
  social: "Connection",
  communication: "Communication",
  "hidden-self": "Self Discovery",
  decision: "Decision",
};

export function categoryForSlug(slug: string): ExploreCategory {
  return SLUG_TO_CATEGORY[slug] ?? "Self Discovery";
}
