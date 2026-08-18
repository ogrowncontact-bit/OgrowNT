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

  // Added for the relationship/jealousy/intimacy/vulnerability/connection/
  // social/communication/hidden-self/decision assessments — genuinely new
  // axes those experiences need, not covered by the dimensions above.
  { key: "expectations", label: "Expectations", description: "How strongly someone holds a relationship to a specific standard or ideal, versus letting it unfold on its own terms." },
  { key: "comparison", label: "Comparison", description: "How much someone measures their relationship or their own standing against others." },
  { key: "uncertainty", label: "Uncertainty Tolerance", description: "How comfortable someone is not knowing something, rather than needing it resolved." },
  { key: "emotional_regulation", label: "Emotional Regulation", description: "How someone manages an emotional reaction once it's triggered, separate from what triggered it." },
  { key: "boundaries", label: "Boundaries", description: "How clearly someone maintains and communicates personal limits with people they're close to." },
  { key: "self_protection", label: "Self-Protection", description: "How actively someone guards against emotional harm, distinct from simply wanting independence." },
  { key: "help_seeking", label: "Help-Seeking", description: "Willingness to ask for and accept support from other people." },
  { key: "novelty", label: "Novelty", description: "Appetite for new experiences and unfamiliar dynamics within a connection." },
  { key: "spontaneity", label: "Spontaneity", description: "Comfort acting on impulse rather than planning things out in advance." },
  { key: "approachability", label: "Approachability", description: "How easy someone seems to approach or start a conversation with, based on their own responses." },
  { key: "assertiveness", label: "Assertiveness", description: "How directly someone states their position and holds it under pressure." },
  { key: "social_awareness", label: "Social Awareness", description: "Attunement to how one's own behavior is landing with the people around them." },
  { key: "first_impression", label: "First Impression", description: "How someone believes they come across to people who don't know them yet." },
  { key: "directness", label: "Directness", description: "How plainly someone states what they mean, versus softening or implying it." },
  { key: "listening", label: "Listening", description: "How attentively someone receives and reflects back what other people communicate." },
  { key: "diplomacy", label: "Diplomacy", description: "Tendency to soften, cushion, or carefully time a difficult message." },
  { key: "openness", label: "Openness to Others", description: "Receptiveness to other people's perspectives, feedback, and ways of communicating." },
  { key: "interpretation", label: "Interpretation", description: "Tendency to read between the lines or assume meaning that wasn't explicitly stated." },
  { key: "recognition", label: "Recognition", description: "How much someone is driven by being seen, credited, or acknowledged for who they are or what they do." },
  { key: "analysis", label: "Analysis", description: "Reliance on structured reasoning and weighing options before deciding." },
  { key: "intuition", label: "Intuition", description: "Reliance on gut feeling and instinct over deliberate analysis." },
  { key: "certainty", label: "Certainty", description: "How much someone needs to feel sure before committing to a decision." },
  { key: "speed", label: "Decision Speed", description: "How quickly someone tends to move from noticing a decision to acting on it." },
  { key: "emotional_influence", label: "Emotional Influence", description: "How much felt emotion shapes a final decision, versus being deliberately set aside." },
  { key: "action", label: "Action Orientation", description: "Tendency to act on a decision immediately, rather than continuing to deliberate." },
];
