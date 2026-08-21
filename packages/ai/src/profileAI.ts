import { callStructured, isAiEnabled } from "./client";
import { enforceNonDiagnostic } from "./guardrails/nonDiagnosticFilter";
import { containsAbsoluteClaim } from "./reportQualityValidator";
import { resolveModelConfig, type AIModelConfig } from "./modelConfig";

interface GenerateInsightParams {
  primaryProfileName: string;
  primaryProfileDescription: string;
  dimensionScores: Record<string, number>; // key -> normalized 0-100
  openAnswerTags: string[];
}

export interface GeneratedInsight {
  insight: string;
  aiGenerated: boolean;
}

/**
 * Narrates the *already-decided* primary profile (from the deterministic
 * matcher) into one personalized sentence for the free result screen. Never
 * chooses the profile itself — see docs/ARCHITECTURE.md §6. Falls back to
 * `null` (caller uses the assessment's static template copy) if AI is
 * unavailable or the output can't be made to pass the non-diagnostic filter.
 */
export async function generateFreeInsight(params: GenerateInsightParams, modelConfig?: Partial<AIModelConfig>): Promise<GeneratedInsight | null> {
  if (!isAiEnabled()) return null;
  const config = resolveModelConfig(modelConfig);

  const scoreLines = Object.entries(params.dimensionScores)
    .map(([dim, score]) => `${dim}: ${Math.round(score)}/100`)
    .join(", ");

  const result = await callStructured<{ insight: string }>({
    module: "profileAI",
    model: config.qualityModel,
    system:
      "You write one short, warm, specific sentence (max 240 characters) for a self-reflection app's free " +
      "result screen. The person's dominant pattern has ALREADY been determined — you are narrating it, " +
      "not diagnosing anything new. Use hedged language: 'your responses suggest...', 'you appear to...', " +
      "'one pattern in your answers is...'. Never say 'you are', 'you have', or use clinical/diagnostic " +
      "terms (disorder, syndrome, diagnosis, trauma, narcissistic, codependent, etc). Never claim certainty " +
      "or that this is a fixed trait. Be specific to their scores, not generic.",
    userMessage: `Primary pattern: ${params.primaryProfileName}\nBase description: ${params.primaryProfileDescription}\nDimension scores: ${scoreLines}\nThemes from their own words: ${params.openAnswerTags.join(", ") || "(none)"}`,
    toolName: "write_insight",
    toolDescription: "Record the one-sentence personalized insight.",
    inputSchema: {
      type: "object",
      properties: { insight: { type: "string", maxLength: 320 } },
      required: ["insight"],
    },
    maxTokens: 200,
    ceilingTokens: config.maxTokens,
    temperature: config.temperature,
    timeoutMs: config.timeoutMs,
  });

  if (!result.ok || !result.data.insight) return null;

  const filtered = enforceNonDiagnostic(result.data.insight);
  if (!filtered.ok) return null; // don't guess at a rewrite for hard-banned clinical terms — fall back to static copy
  if (containsAbsoluteClaim(filtered.text)) return null; // "always"/"never"/"guaranteed" — same quality bar the premium report enforces

  return { insight: filtered.text, aiGenerated: true };
}
