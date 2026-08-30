import { prisma } from "@inner/db";
import type { QaResult } from "@/lib/qa/runLoveQaSimulation";

export interface QaRunSummary {
  id: string;
  createdAt: Date;
  result: QaResult;
}

/** Latest QA simulation run for any assessment slug — the underlying QaSimulationRun table has always been slug-scoped (FASE 31), this reader just wasn't generalized past LOVE until now. */
export async function getLatestQaRun(slug: string): Promise<QaRunSummary | null> {
  const run = await prisma.qaSimulationRun.findFirst({
    where: { assessmentSlug: slug },
    orderBy: { createdAt: "desc" },
  });
  if (!run) return null;
  return { id: run.id, createdAt: run.createdAt, result: run.resultJson as unknown as QaResult };
}

/** @deprecated kept for any existing import sites — prefer getLatestQaRun("love"). */
export async function getLatestLoveQaRun(): Promise<QaRunSummary | null> {
  return getLatestQaRun("love");
}
