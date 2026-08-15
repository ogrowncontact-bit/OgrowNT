import { callStructured, isAiEnabled, MODELS } from "./client";

export interface FollowupCandidate {
  key: string;
  prompt: string;
}

interface ChooseFollowupParams {
  answerText: string;
  tags: string[];
  candidates: FollowupCandidate[];
}

export interface FollowupChoice {
  chosenKey: string | null;
  aiGenerated: boolean;
}

/**
 * Picks at most one follow-up from a fixed, assessment-approved candidate
 * list (never invents a new question) — this is the "AI identifies
 * ambiguity → follow-up" behavior from the product spec, constrained per
 * docs/ARCHITECTURE.md §4 so it can only select, not author, new
 * psychological territory.
 */
export async function chooseFollowup(params: ChooseFollowupParams): Promise<FollowupChoice> {
  if (params.candidates.length === 0) return { chosenKey: null, aiGenerated: false };

  if (!isAiEnabled()) {
    return { chosenKey: fallbackChoice(params), aiGenerated: false };
  }

  const result = await callStructured<{ chosen_key: string }>({
    model: MODELS.fast,
    system:
      "You decide whether one more follow-up question is worth asking in a short self-reflection " +
      "interview about relationship patterns. You may ONLY pick from the exact candidate keys given, " +
      "or 'none' if the answer was already clear enough that a follow-up wouldn't add anything. " +
      "Never suggest a question that isn't in the candidate list.",
    userMessage: `Answer: "${params.answerText}"\nTags: ${params.tags.join(", ") || "(none)"}\n\nCandidates:\n${params.candidates
      .map((c) => `- ${c.key}: "${c.prompt}"`)
      .join("\n")}\n- none: skip the follow-up`,
    toolName: "choose_followup",
    toolDescription: "Record which follow-up question (if any) to ask next.",
    inputSchema: {
      type: "object",
      properties: {
        chosen_key: { type: "string", enum: [...params.candidates.map((c) => c.key), "none"] },
      },
      required: ["chosen_key"],
    },
    maxTokens: 100,
  });

  if (!result.ok) return { chosenKey: fallbackChoice(params), aiGenerated: false };

  const chosen = result.data.chosen_key;
  const isValidCandidate = params.candidates.some((c) => c.key === chosen);
  return { chosenKey: isValidCandidate ? chosen : null, aiGenerated: true };
}

/** Simple keyword heuristic used only when the model is unavailable — honest fallback, not a substitute for real interpretation. */
function fallbackChoice(params: ChooseFollowupParams): string | null {
  const text = params.answerText.toLowerCase();
  const mentionsHistory = /\b(again|before|used to|every time|always|pattern|history|past relationship)\b/.test(text);
  const byKey = new Map(params.candidates.map((c) => [c.key, c]));

  if (mentionsHistory && byKey.has("what_pattern_notice")) return "what_pattern_notice";
  if (byKey.has("what_would_help")) return "what_would_help";
  return params.candidates[0]?.key ?? null;
}
