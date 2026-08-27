import { prisma } from "@inner/db";
import { setAiForceFallback } from "@inner/ai";

const FLAGS_ID = "singleton";

export interface EmergencyControlsState {
  purchasesPaused: boolean;
  reportGenerationPaused: boolean;
  aiForceFallback: boolean;
  updatedAt: Date | null;
  updatedByAdminId: string | null;
}

/**
 * FASE 33 §EMERGENCY CONTROLS — falls back to "everything on" (no row saved
 * yet) rather than hard-failing, matching the AiSettings/getAiModelConfig
 * pattern: a fresh install must never behave as if every switch were paused.
 */
export async function getEmergencyControls(): Promise<EmergencyControlsState> {
  const row = await prisma.featureFlags.findUnique({ where: { id: FLAGS_ID } });
  return {
    purchasesPaused: row?.purchasesPaused ?? false,
    reportGenerationPaused: row?.reportGenerationPaused ?? false,
    aiForceFallback: row?.aiForceFallback ?? false,
    updatedAt: row?.updatedAt ?? null,
    updatedByAdminId: row?.updatedByAdminId ?? null,
  };
}

export interface UpdateEmergencyControlsInput {
  purchasesPaused: boolean;
  reportGenerationPaused: boolean;
  aiForceFallback: boolean;
  updatedByAdminId: string;
}

export async function updateEmergencyControls(input: UpdateEmergencyControlsInput): Promise<EmergencyControlsState> {
  const row = await prisma.featureFlags.upsert({
    where: { id: FLAGS_ID },
    update: {
      purchasesPaused: input.purchasesPaused,
      reportGenerationPaused: input.reportGenerationPaused,
      aiForceFallback: input.aiForceFallback,
      updatedByAdminId: input.updatedByAdminId,
    },
    create: {
      id: FLAGS_ID,
      purchasesPaused: input.purchasesPaused,
      reportGenerationPaused: input.reportGenerationPaused,
      aiForceFallback: input.aiForceFallback,
      updatedByAdminId: input.updatedByAdminId,
    },
  });
  return {
    purchasesPaused: row.purchasesPaused,
    reportGenerationPaused: row.reportGenerationPaused,
    aiForceFallback: row.aiForceFallback,
    updatedAt: row.updatedAt,
    updatedByAdminId: row.updatedByAdminId,
  };
}

/**
 * Call once at the top of any request path that may invoke AI (live
 * assessment answers, report generation) so packages/ai's isAiEnabled()
 * reflects the current admin-set switch without a redeploy.
 */
export async function applyAiForceFallback(): Promise<void> {
  const flags = await getEmergencyControls();
  setAiForceFallback(flags.aiForceFallback);
}
