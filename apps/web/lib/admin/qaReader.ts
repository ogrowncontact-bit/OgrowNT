import { prisma } from "@inner/db";
import type { LoveQaResult } from "@/lib/qa/runLoveQaSimulation";

export interface QaRunSummary {
  id: string;
  createdAt: Date;
  result: LoveQaResult;
}

export async function getLatestLoveQaRun(): Promise<QaRunSummary | null> {
  const run = await prisma.qaSimulationRun.findFirst({
    where: { assessmentSlug: "love" },
    orderBy: { createdAt: "desc" },
  });
  if (!run) return null;
  return { id: run.id, createdAt: run.createdAt, result: run.resultJson as unknown as LoveQaResult };
}
