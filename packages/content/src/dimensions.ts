// Global, reusable dimension pool — docs/ARCHITECTURE.md §3. Individual
// assessments reference a subset of these by key; scores stay comparable
// across assessments because the pool (and its normalization) is shared.

export interface DimensionDefinition {
  key: string;
  label: string;
  description: string;
}

export const dimensionPool: DimensionDefinition[] = [
  { key: "connection", label: "Connection", description: "How much closeness and togetherness someone seeks in relationships." },
  { key: "independence", label: "Independence", description: "How strongly someone protects autonomy and personal space." },
  { key: "trust", label: "Trust", description: "How readily someone extends trust and believes in others' intentions." },
  { key: "vulnerability", label: "Vulnerability", description: "How openly someone shares emotions and uncertainties." },
  { key: "emotional_openness", label: "Emotional Openness", description: "How freely someone expresses what they feel in the moment." },
  { key: "validation", label: "Validation", description: "How much someone relies on external reassurance." },
  { key: "conflict", label: "Conflict", description: "How someone tends to engage with (or avoid) disagreement." },
  { key: "control", label: "Control", description: "How much someone needs to steer outcomes rather than let things unfold." },
  { key: "risk", label: "Risk", description: "Comfort with emotional or relational uncertainty." },
  { key: "communication", label: "Communication", description: "Directness and clarity in expressing needs." },
  { key: "social_confidence", label: "Social Confidence", description: "Ease in social and interpersonal situations." },
  { key: "security", label: "Security", description: "Underlying sense of safety in relationships." },
  { key: "curiosity", label: "Curiosity", description: "Interest in exploring the unfamiliar with others." },
  { key: "flexibility", label: "Flexibility", description: "Willingness to adapt expectations to another person." },
  { key: "affection_expression", label: "Affection Expression", description: "How openly and directly someone shows care once they feel it." },
  { key: "distance_response", label: "Distance Response", description: "How someone tends to react when a person they're close to becomes less available." },
];
