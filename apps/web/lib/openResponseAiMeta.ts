/** Shape stored in OpenResponse.aiTags — grouping everything Response AI / Question AI produced for one open-text answer, so no schema migration was needed to add Phase 2's AI layer. */
export interface OpenResponseAiMeta {
  tags: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  dimensionNudges: Record<string, number>;
  chosenFollowupKey?: string;
  aiGenerated: boolean;
  /** Response AI's own confidence in this extraction (0..1) — see packages/ai/src/responseAI.ts. */
  confidence: number;
}
