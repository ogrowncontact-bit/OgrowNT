import { callStructured, isAiEnabled, MODELS } from "./client";
import { enforceNonDiagnostic } from "./guardrails/nonDiagnosticFilter";

interface GenerateRecommendationParams {
  fromAssessmentName: string;
  primaryProfileName: string;
  topDimensionLabel: string;
  targetAssessmentName: string;
  targetAssessmentHook: string;
}

export interface GeneratedRecommendation {
  bridgeCopy: string;
  aiGenerated: boolean;
}

/**
 * Writes the 1-2 sentence bridge between a just-completed experience and
 * the next one — never chooses *which* experience, that's decided
 * deterministically first (apps/web/lib/recommendation.ts) from
 * config-declared candidates only, so this can't recommend something
 * irrelevant or unpublished. See docs/ARCHITECTURE.md §8.
 */
export async function generateRecommendationCopy(params: GenerateRecommendationParams): Promise<GeneratedRecommendation | null> {
  if (!isAiEnabled()) return null;

  const result = await callStructured<{ bridge_copy: string }>({
    module: "recommendationAI",
    model: MODELS.fast,
    system:
      "You write one warm, specific sentence bridging a just-completed self-reflection experience to a " +
      "related one, for a premium app. It should feel like a natural next question the person might have " +
      "about themselves, not an advertisement. Never claim certainty about what the next experience will " +
      "reveal. Use hedged language ('your answers showed...', 'curious how...'). Max 200 characters.",
    userMessage:
      `They just finished "${params.fromAssessmentName}" and their primary pattern was ${params.primaryProfileName}, ` +
      `with ${params.topDimensionLabel} standing out most.\n` +
      `The next experience is "${params.targetAssessmentName}": ${params.targetAssessmentHook}`,
    toolName: "write_bridge",
    toolDescription: "Record the bridge sentence.",
    inputSchema: {
      type: "object",
      properties: { bridge_copy: { type: "string", maxLength: 240 } },
      required: ["bridge_copy"],
    },
    maxTokens: 150,
  });

  if (!result.ok || !result.data.bridge_copy) return null;
  const filtered = enforceNonDiagnostic(result.data.bridge_copy.trim());
  if (!filtered.ok) return null;

  return { bridgeCopy: filtered.text, aiGenerated: true };
}
