import { MODELS } from "./client";

/**
 * Admin-tunable knobs for every AI call in this package. packages/ai has no
 * persistence of its own (see telemetry.ts) — apps/web reads its `AiSettings`
 * singleton row and passes it in here. Never includes an API key: that stays
 * an env var (see client.ts's isAiEnabled/getClient), never a DB column an
 * admin UI could echo back.
 */
export interface AIModelConfig {
  fastModel: string;
  qualityModel: string;
  temperature: number;
  maxTokens: number;
  timeoutMs: number;
}

export const DEFAULT_MODEL_CONFIG: AIModelConfig = {
  fastModel: MODELS.fast,
  qualityModel: MODELS.quality,
  temperature: 1.0,
  maxTokens: 4096,
  timeoutMs: 30_000,
};

export function resolveModelConfig(partial?: Partial<AIModelConfig>): AIModelConfig {
  if (!partial) return DEFAULT_MODEL_CONFIG;
  return { ...DEFAULT_MODEL_CONFIG, ...partial };
}
