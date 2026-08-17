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
    module: "questionAI",
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

const STOP_WORDS = new Set([
  "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "is", "was", "were",
  "it", "i", "you", "me", "my", "your", "this", "that", "at", "be", "as", "so", "not", "just", "really",
]);

function words(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP_WORDS.has(w));
}

/**
 * Generic word-overlap heuristic used only when the model is unavailable —
 * scores each candidate by vocabulary overlap between its own prompt and
 * the answer text, rather than hardcoding any assessment's specific
 * candidate keys (every assessment names its candidates differently).
 * Honest fallback, not a substitute for real interpretation.
 */
function fallbackChoice(params: ChooseFollowupParams): string | null {
  if (params.candidates.length === 1) return params.candidates[0].key;

  const answerWords = new Set(words(params.answerText));
  if (answerWords.size === 0) return params.candidates[0]?.key ?? null;

  let best = params.candidates[0];
  let bestScore = -1;
  for (const candidate of params.candidates) {
    const overlap = words(candidate.prompt).filter((w) => answerWords.has(w)).length;
    if (overlap > bestScore) {
      bestScore = overlap;
      best = candidate;
    }
  }
  return best?.key ?? null;
}
