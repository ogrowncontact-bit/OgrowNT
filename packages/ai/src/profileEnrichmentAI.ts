import { callStructured, isAiEnabled } from "./client";
import { enforceNonDiagnostic } from "./guardrails/nonDiagnosticFilter";
import { resolveModelConfig, type AIModelConfig } from "./modelConfig";
import { bucketConfidence } from "./confidence";

export type InsightType = "strength" | "friction" | "pattern" | "contradiction";

export interface EnrichedInsight {
  type: InsightType;
  text: string;
  confidence: number; // 0..1
}

export interface ProfileEnrichment {
  themes: string[];
  insights: EnrichedInsight[];
  aiGenerated: boolean;
}

export interface DimensionInput {
  key: string;
  label: string;
  normalized: number; // 0..100
  confidence: number; // 0..1
}

export interface TensionInput {
  key: string;
  label: string;
  dimensions: [string, string];
  strength: number; // 0..1
}

export interface ContradictionInput {
  dimensionKey: string;
  label: string;
  /** 0..1 — how strongly the contributing answers disagreed in direction (1 - consistency). Deterministic, from assessment-engine's detectContradictions(). */
  strength: number;
}

interface EnrichProfileParams {
  primaryProfileName: string;
  secondaryProfileNames: string[];
  dimensions: DimensionInput[];
  tensions: TensionInput[];
  /** Distinct from tensions: two DIFFERENT questions pulling the same dimension in opposite directions, not two dimensions both being strong. */
  contradictions: ContradictionInput[];
  /** Tags already extracted from this session's open-text answers (Response AI) — never raw text. */
  openAnswerThemes: string[];
}

const MAX_INSIGHTS = 5;

/**
 * Enriches an already-decided profile with themes and narrative insights —
 * feeds the future premium report's REPORT INPUT stage. Deliberately
 * downstream of, not a replacement for, the deterministic classification in
 * profileMatcher.ts/scoring.ts: this function receives the primary/secondary
 * profiles and tensions as already-decided facts and only ever elaborates
 * on them. It never re-classifies, and it always returns *something*
 * structured — including with AI unavailable — since the report pipeline
 * needs a REPORT INPUT either way. See docs/ARCHITECTURE.md §6.
 */
export async function enrichProfileWithAI(params: EnrichProfileParams, modelConfig?: Partial<AIModelConfig>): Promise<ProfileEnrichment> {
  if (!isAiEnabled()) {
    return deterministicFallback(params);
  }
  const config = resolveModelConfig(modelConfig);

  const dimensionLines = params.dimensions
    .map((d) => `${d.label} (${d.key}): ${Math.round(d.normalized)}/100, confidence ${d.confidence.toFixed(2)} (${bucketConfidence(d.confidence)})`)
    .join("\n");
  const tensionLines = params.tensions.length
    ? params.tensions.map((t) => `${t.label}: ${t.dimensions.join(" + ")} (strength ${t.strength.toFixed(2)})`).join("\n")
    : "(none detected)";
  const contradictionLines = params.contradictions.length
    ? params.contradictions.map((c) => `${c.label}: answers disagreed in direction (strength ${c.strength.toFixed(2)})`).join("\n")
    : "(none detected)";

  const result = await callStructured<{
    themes: string[];
    insights: { type: string; text: string; confidence: number }[];
  }>({
    module: "profileEnrichmentAI",
    model: config.qualityModel,
    system:
      "You enrich an already-decided personality-pattern profile for a self-reflection app. The primary and " +
      "secondary profiles, dimension scores, and any tensions or contradictions have ALREADY been determined " +
      "by deterministic scoring — you are elaborating on them, never re-deciding or overriding them. Write 2-5 " +
      "short themes (lowercase-hyphenated, e.g. 'protects-independence') and up to 5 short insights (max 200 " +
      "characters each), each tagged 'strength', 'friction', 'pattern', or 'contradiction'. Use 'pattern' for " +
      "tensions (two dimensions both scoring strongly — two things being true at once, not a contradiction). " +
      "Use 'contradiction' only for listed Contradictions, where answers to different questions pulled in " +
      "opposite directions — phrase these especially carefully, e.g. 'you may be emotionally open when you " +
      "feel safe, but become more private under pressure', never as inconsistency, confusion, or dishonesty on " +
      "their part. Use hedged language throughout: 'your responses suggest...', 'you appear to...', 'one " +
      "pattern worth noticing is...', 'in some situations... while in others...'. Never say 'you are' or 'you " +
      "have'. Never use clinical or diagnostic terms (disorder, syndrome, diagnosis, trauma, narcissistic, " +
      "codependent, etc). Give each insight your own confidence (0-1) reflecting how strongly the underlying " +
      "data supports it — a dimension marked low or medium confidence should produce, at most, a matching " +
      "low- or medium-confidence insight, worded more tentatively.",
    userMessage:
      `Primary profile: ${params.primaryProfileName}\n` +
      `Secondary profiles: ${params.secondaryProfileNames.join(", ") || "(none)"}\n\n` +
      `Dimensions:\n${dimensionLines}\n\n` +
      `Tensions:\n${tensionLines}\n\n` +
      `Contradictions (answers to different questions disagreeing — not the same as a tension):\n${contradictionLines}\n\n` +
      `Themes from their own words: ${params.openAnswerThemes.join(", ") || "(none)"}`,
    toolName: "record_enrichment",
    toolDescription: "Record the enriched themes and insights for this profile.",
    inputSchema: {
      type: "object",
      properties: {
        themes: { type: "array", items: { type: "string" }, maxItems: 5 },
        insights: {
          type: "array",
          maxItems: MAX_INSIGHTS,
          items: {
            type: "object",
            properties: {
              type: { type: "string", enum: ["strength", "friction", "pattern", "contradiction"] },
              text: { type: "string", maxLength: 260 },
              confidence: { type: "number", minimum: 0, maximum: 1 },
            },
            required: ["type", "text", "confidence"],
          },
        },
      },
      required: ["themes", "insights"],
    },
    maxTokens: 700,
    ceilingTokens: config.maxTokens,
    temperature: config.temperature,
    timeoutMs: config.timeoutMs,
  });

  if (!result.ok) return deterministicFallback(params);

  const validTypes = new Set<InsightType>(["strength", "friction", "pattern", "contradiction"]);
  const insights: EnrichedInsight[] = (Array.isArray(result.data.insights) ? result.data.insights : [])
    .filter((i) => validTypes.has(i.type as InsightType))
    .map((i) => {
      const filtered = enforceNonDiagnostic(i.text ?? "");
      return filtered.ok
        ? { type: i.type as InsightType, text: filtered.text, confidence: clamp01(i.confidence) }
        : null;
    })
    .filter((i): i is EnrichedInsight => i !== null)
    .slice(0, MAX_INSIGHTS);

  if (insights.length === 0) return deterministicFallback(params);

  return {
    themes: Array.isArray(result.data.themes) ? result.data.themes.slice(0, 5).map(String) : [],
    insights,
    aiGenerated: true,
  };
}

function clamp01(n: unknown): number {
  const v = typeof n === "number" && Number.isFinite(n) ? n : 0;
  return Math.max(0, Math.min(1, v));
}

/**
 * Non-null by design: the report pipeline needs REPORT INPUT whether or not
 * AI is reachable. Built directly from the same structured facts the AI
 * path would have received, so it degrades in richness, not in honesty.
 */
function deterministicFallback(params: EnrichProfileParams): ProfileEnrichment {
  const sortedByStrength = [...params.dimensions].sort(
    (a, b) => Math.abs(b.normalized - 50) - Math.abs(a.normalized - 50)
  );

  const themes =
    params.openAnswerThemes.length > 0
      ? params.openAnswerThemes.slice(0, 5)
      : sortedByStrength.slice(0, 2).map((d) => d.key.replace(/_/g, "-"));

  const insights: EnrichedInsight[] = [];

  const strongest = [...params.dimensions].filter((d) => d.normalized > 60).sort((a, b) => b.normalized - a.normalized)[0];
  if (strongest) {
    insights.push({
      type: "strength",
      text: `Your responses suggest real strength in ${strongest.label.toLowerCase()}.`,
      confidence: strongest.confidence,
    });
  }

  const weakest = [...params.dimensions].filter((d) => d.normalized < 40).sort((a, b) => a.normalized - b.normalized)[0];
  if (weakest) {
    insights.push({
      type: "friction",
      text: `One pattern worth noticing: ${weakest.label.toLowerCase()} scored lower relative to your other patterns.`,
      confidence: weakest.confidence,
    });
  }

  const strongestTension = params.tensions[0];
  if (strongestTension) {
    insights.push({
      type: "pattern",
      text: `Your responses suggest two things are true for you at once: ${strongestTension.label.toLowerCase()}.`,
      confidence: strongestTension.strength,
    });
  }

  const strongestContradiction = params.contradictions[0];
  if (strongestContradiction) {
    insights.push({
      type: "contradiction",
      text: `Your answers didn't point the same way on ${strongestContradiction.label.toLowerCase()} — this can depend a lot on the situation, rather than being one fixed pattern.`,
      confidence: strongestContradiction.strength,
    });
  }

  return { themes, insights: insights.slice(0, MAX_INSIGHTS), aiGenerated: false };
}
