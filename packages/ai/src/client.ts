import Anthropic from "@anthropic-ai/sdk";
import { reportAiCall } from "./telemetry";

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
  /** Which AI module this is (§4 — "questionAI", "responseAI", "profileAI", "reportAI", "recommendationAI"), for cost/latency monitoring (§7). */
  module: string;
  model: string;
  system: string;
  userMessage: string;
  toolName: string;
  toolDescription: string;
  inputSchema: Record<string, unknown>;
  /** Requested by the call site; still capped by `ceilingTokens` (the admin's configured maxTokens) below. */
  maxTokens?: number;
  /** Admin-configured ceiling — the call site's `maxTokens` is clamped to this, never the other way around. */
  ceilingTokens?: number;
  temperature?: number;
  timeoutMs?: number;
}

/** One Claude call, forced to answer via a single tool call so the output is structured, not free-text we'd have to parse. Every call — including the no-API-key and error paths — is reported via reportAiCall() for cost/latency monitoring. */
export async function callStructured<T>(params: CallStructuredParams): Promise<StructuredResult<T>> {
  const anthropic = getClient();
  if (!anthropic) {
    const reason = "AI disabled (no ANTHROPIC_API_KEY)";
    reportAiCall({ module: params.module, model: params.model, latencyMs: 0, inputTokens: null, outputTokens: null, ok: false, errorReason: reason });
    return { ok: false, reason };
  }

  const start = Date.now();
  try {
    const requestedTokens = params.maxTokens ?? 512;
    const maxTokens = params.ceilingTokens ? Math.min(requestedTokens, params.ceilingTokens) : requestedTokens;
    const response = await anthropic.messages.create(
      {
        model: params.model,
        max_tokens: maxTokens,
        temperature: params.temperature,
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
      },
      params.timeoutMs ? { timeout: params.timeoutMs } : undefined,
    );
    const latencyMs = Date.now() - start;
    const inputTokens = response.usage?.input_tokens ?? null;
    const outputTokens = response.usage?.output_tokens ?? null;

    const toolUse = response.content.find((block) => block.type === "tool_use");
    if (!toolUse || toolUse.type !== "tool_use") {
      const reason = "Model did not return a tool_use block";
      reportAiCall({ module: params.module, model: params.model, latencyMs, inputTokens, outputTokens, ok: false, errorReason: reason });
      return { ok: false, reason };
    }
    reportAiCall({ module: params.module, model: params.model, latencyMs, inputTokens, outputTokens, ok: true, errorReason: null });
    return { ok: true, data: toolUse.input as T };
  } catch (error) {
    const latencyMs = Date.now() - start;
    const reason = error instanceof Error ? error.message : "Unknown AI error";
    reportAiCall({ module: params.module, model: params.model, latencyMs, inputTokens: null, outputTokens: null, ok: false, errorReason: reason });
    return { ok: false, reason };
  }
}
