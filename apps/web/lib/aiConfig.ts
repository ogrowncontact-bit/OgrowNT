import { prisma } from "@inner/db";
import { DEFAULT_MODEL_CONFIG, type AIModelConfig } from "@inner/ai";

const SETTINGS_ID = "singleton";

/**
 * Reads the admin-configured AI model settings, falling back to packages/ai's
 * own defaults when no row has been saved yet (fresh install) — AI
 * generation must never hard-fail just because nobody's opened the settings
 * page. Never reads or returns an API key: that's ANTHROPIC_API_KEY only,
 * never a DB column an admin UI could echo back. See docs/ARCHITECTURE.md §4.
 */
export async function getAiModelConfig(): Promise<AIModelConfig> {
  const row = await prisma.aiSettings.findUnique({ where: { id: SETTINGS_ID } });
  if (!row) return DEFAULT_MODEL_CONFIG;
  return {
    fastModel: row.fastModel,
    qualityModel: row.qualityModel,
    temperature: row.temperature,
    maxTokens: row.maxTokens,
    timeoutMs: row.timeoutMs,
  };
}

export interface UpdateAiSettingsInput extends AIModelConfig {
  updatedByAdminId: string;
}

export async function updateAiSettings(input: UpdateAiSettingsInput): Promise<AIModelConfig> {
  const row = await prisma.aiSettings.upsert({
    where: { id: SETTINGS_ID },
    update: {
      fastModel: input.fastModel,
      qualityModel: input.qualityModel,
      temperature: input.temperature,
      maxTokens: input.maxTokens,
      timeoutMs: input.timeoutMs,
      updatedByAdminId: input.updatedByAdminId,
    },
    create: {
      id: SETTINGS_ID,
      fastModel: input.fastModel,
      qualityModel: input.qualityModel,
      temperature: input.temperature,
      maxTokens: input.maxTokens,
      timeoutMs: input.timeoutMs,
      updatedByAdminId: input.updatedByAdminId,
    },
  });
  return {
    fastModel: row.fastModel,
    qualityModel: row.qualityModel,
    temperature: row.temperature,
    maxTokens: row.maxTokens,
    timeoutMs: row.timeoutMs,
  };
}
