import Anthropic from "@anthropic-ai/sdk";

/**
 * Every AI module in this package goes through here, and every call is
 * try/catch-wrapped so a missing key, a network failure, or a malformed
 * response degrades to `{ ok: false }` rather than throwing — nothing in
 * apps/web is allowed to assume the AI is reachable. See
 * docs/ARCHITECTURE.md §4 ("AI must never be the only source of truth").
 */
export const MODELS = {
  /** Question AI, Response AI — fast/cheap, sits in the live conversation's critical path. */
  fast: "claude-haiku-4-5-20251001",
  /** Profile AI, (later) Report AI — generation quality matters more than latency. */
  quality: "claude-sonnet-5",
} as const;

let client: Anthropic | null | undefined;

export function isAiEnabled(): boolean {
  return !!process.env.ANTHROPIC_API_KEY;
}

function getClient(): Anthropic | null {
  if (client !== undefined) return client;
  client = process.env.ANTHROPIC_API_KEY ? new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY }) : null;
  return client;
}

export type StructuredResult<T> = { ok: true; data: T } | { ok: false; reason: string };

interface CallStructuredParams {
  model: string;
  system: string;
  userMessage: string;
  toolName: string;
  toolDescription: string;
  inputSchema: Record<string, unknown>;
  maxTokens?: number;
}

/** One Claude call, forced to answer via a single tool call so the output is structured, not free-text we'd have to parse. */
export async function callStructured<T>(params: CallStructuredParams): Promise<StructuredResult<T>> {
  const anthropic = getClient();
  if (!anthropic) return { ok: false, reason: "AI disabled (no ANTHROPIC_API_KEY)" };

  try {
    const response = await anthropic.messages.create({
      model: params.model,
      max_tokens: params.maxTokens ?? 512,
      system: params.system,
      messages: [{ role: "user", content: params.userMessage }],
      tools: [
        {
          name: params.toolName,
          description: params.toolDescription,
          input_schema: params.inputSchema as Anthropic.Tool.InputSchema,
        },
      ],
      tool_choice: { type: "tool", name: params.toolName },
    });

    const toolUse = response.content.find((block) => block.type === "tool_use");
    if (!toolUse || toolUse.type !== "tool_use") {
      return { ok: false, reason: "Model did not return a tool_use block" };
    }
    return { ok: true, data: toolUse.input as T };
  } catch (error) {
    return { ok: false, reason: error instanceof Error ? error.message : "Unknown AI error" };
  }
}
