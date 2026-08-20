/**
 * Layer 5 "REPORT OBJECTIVE" — what a given report section must accomplish,
 * plus the semantic "role" the section plays in a ReportDocument (see
 * ../reportDocument.ts). All 10 assessment configs converge on the same
 * common section-key vocabulary (signature, dominant_pattern, strengths,
 * a friction-type key, inner_tension, reflection, final_note) around 3-5
 * assessment-specific narrative sections in between — this registry is
 * built directly from that convention rather than inventing a new one, so
 * every already-authored premiumReportStructure keeps working unchanged.
 */
export type SectionRole =
  | "signature"
  | "core_pattern"
  | "strengths"
  | "friction"
  | "tension"
  | "how_you_come_across"
  | "under_pressure"
  | "reflection"
  | "closing"
  | "narrative";

interface SectionObjectiveEntry {
  role: SectionRole;
  objective: string;
}

const KEY_REGISTRY: Record<string, SectionObjectiveEntry> = {
  signature: { role: "signature", objective: "State the person's primary pattern name and give one grounded, specific sentence of what it means for them." },
  dominant_pattern: { role: "core_pattern", objective: "Explain the dominant pattern — which dimension shapes it most, and how that shows up in practice." },
  strengths: { role: "strengths", objective: "Highlight a useful tendency, grounded in their actual scores — never a generic compliment." },
  friction_points: { role: "friction", objective: "Describe possible friction without judgment — a situation or misunderstanding their pattern could create." },
  blind_spots: { role: "friction", objective: "Describe a possible blind spot without judgment — something their pattern might make harder to see in themselves." },
  possible_blind_spots: { role: "friction", objective: "Describe a possible blind spot without judgment — something their pattern might make harder to see in themselves." },
  inner_tension: { role: "tension", objective: "Explain the interaction between two dimensions — how they complement each other and when they might pull in different directions." },
  recurring_tension: { role: "tension", objective: "Explain a recurring tension between two dimensions — how they complement each other and when they might pull in different directions." },
  misunderstood_aspects: { role: "how_you_come_across", objective: "Describe how this pattern may come across to others, without claiming to know what anyone actually thinks." },
  perception: { role: "how_you_come_across", objective: "Describe how this pattern may come across to others, without claiming to know what anyone actually thinks." },
  how_others_may_read_you: { role: "how_you_come_across", objective: "Describe how this pattern may come across to others, without claiming to know what anyone actually thinks." },
  first_impression_analysis: { role: "how_you_come_across", objective: "Describe how this pattern may come across to others, without claiming to know what anyone actually thinks." },
  the_gap: { role: "how_you_come_across", objective: "Describe any gap between how they see themselves and what their answers suggest comes across." },
  how_you_react: { role: "under_pressure", objective: "Explain how this tendency may shift under uncertainty, conflict, or emotional pressure." },
  reflection: { role: "reflection", objective: "Offer reflective questions — do not answer them, invite the reader to sit with them." },
  final_note: { role: "closing", objective: "Close warmly: this is a snapshot of a pattern today, not a fixed label, and it can shift with attention." },
  conclusion: { role: "closing", objective: "Close warmly: this is a snapshot of a pattern today, not a fixed label, and it can shift with attention." },
};

/** Falls back to inferring a generic narrative objective from the section's own title — every admin-authored custom key still gets a sensible Layer 5, never an empty one. */
export function sectionObjectiveFor(key: string, title: string): { role: SectionRole; objective: string } {
  const known = KEY_REGISTRY[key];
  if (known) return known;
  return {
    role: "narrative",
    objective: `Write this section, titled "${title}", specific to this person's actual scores — connect at least two of their dimensions rather than describing either in isolation.`,
  };
}
