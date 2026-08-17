import { callStructured, isAiEnabled, MODELS } from "./client";
import { detectSafetyConcern } from "./guardrails/safetyFlag";

export interface OpenAnswerAnalysis {
  tags: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  /** Bounded -1..1 per dimension; scoring.ts further caps total influence via scoringModel.aiInfluenceCap. */
  dimensionNudges: Record<string, number>;
  safetyFlag: boolean;
  aiGenerated: boolean;
}

interface InterpretParams {
  questionPrompt: string;
  answerText: string;
  /** Allow-list — the model may only nudge dimensions this assessment actually uses. */
  allowedDimensions: string[];
}

const TOOL_NAME = "record_analysis";

function clamp(n: unknown): number {
  const v = typeof n === "number" && Number.isFinite(n) ? n : 0;
  return Math.max(-1, Math.min(1, v));
}

/**
 * Interprets a single open-text answer. Never the sole source of truth: the
 * caller blends `dimensionNudges` into an already-computed structured score
 * under a hard cap, and `safetyFlag` is OR'd with the deterministic keyword
 * check below, which always wins on its own regardless of what the model says.
 */
export async function interpretOpenAnswer(params: InterpretParams): Promise<OpenAnswerAnalysis> {
  const deterministicSafetyFlag = detectSafetyConcern(params.answerText);

  if (!isAiEnabled()) {
    return { tags: [], sentiment: "neutral", dimensionNudges: {}, safetyFlag: deterministicSafetyFlag, aiGenerated: false };
  }

  const result = await callStructured<{
    tags: string[];
    sentiment: string;
    dimension_nudges: Record<string, number>;
    safety_concern: boolean;
  }>({
    module: "responseAI",
    model: MODELS.fast,
    system:
      "You analyze one short, personal answer from a self-reflection app about relationship patterns. " +
      "You are not a therapist and must never diagnose, label a disorder, or make definitive claims about " +
      "the person. Extract only: 2-5 short lowercase-hyphenated tags describing the pattern hinted at " +
      "(e.g. 'protects-independence', 'fears-rejection'), an overall sentiment, small nudges (-1 to 1) " +
      "for how strongly this answer leans toward each allowed dimension (0 if not relevant), and whether " +
      "the answer discloses something concerning like self-harm, suicidal thoughts, or abuse. " +
      "Never invent dimensions outside the allowed list.",
    userMessage: `Question: "${params.questionPrompt}"\nAnswer: "${params.answerText}"\nAllowed dimensions: ${params.allowedDimensions.join(", ")}`,
    toolName: TOOL_NAME,
    toolDescription: "Record the structured analysis of this open-text answer.",
    inputSchema: {
      type: "object",
      properties: {
        tags: { type: "array", items: { type: "string" }, maxItems: 5 },
        sentiment: { type: "string", enum: ["positive", "neutral", "negative", "mixed"] },
        dimension_nudges: {
          type: "object",
          properties: Object.fromEntries(params.allowedDimensions.map((d) => [d, { type: "number", minimum: -1, maximum: 1 }])),
        },
        safety_concern: { type: "boolean" },
      },
      required: ["tags", "sentiment", "dimension_nudges", "safety_concern"],
    },
    maxTokens: 400,
  });

  if (!result.ok) {
    return { tags: [], sentiment: "neutral", dimensionNudges: {}, safetyFlag: deterministicSafetyFlag, aiGenerated: false };
  }

  const nudges: Record<string, number> = {};
  for (const dim of params.allowedDimensions) {
    const raw = result.data.dimension_nudges?.[dim];
    if (raw !== undefined) nudges[dim] = clamp(raw);
  }

  const sentiment = (["positive", "neutral", "negative", "mixed"] as const).includes(result.data.sentiment as any)
    ? (result.data.sentiment as OpenAnswerAnalysis["sentiment"])
    : "neutral";

  return {
    tags: Array.isArray(result.data.tags) ? result.data.tags.slice(0, 5).map(String) : [],
    sentiment,
    dimensionNudges: nudges,
    // the deterministic keyword check always wins if it fired, even when the model misses it
    safetyFlag: deterministicSafetyFlag || result.data.safety_concern === true,
    aiGenerated: true,
  };
}
