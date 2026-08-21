import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { requireAdminWriter } from "@/lib/adminAuth";
import { checkRateLimit } from "@/lib/security/rateLimit";
import { logAdminAction } from "@/lib/auditLog";
import { runLoveQaSimulation } from "@/lib/qa/runLoveQaSimulation";

/**
 * FASE 31 §100-PERSONA QA SIMULATION — admin-gated trigger. Runs ~100
 * synthetic sessions through the real engine (see runLoveQaSimulation.ts)
 * and persists the aggregate result so /admin/qa/love can render it without
 * re-running on every page view. Rate-limited: each run does real DB work
 * across ~100 sessions and is meant to be triggered deliberately, not
 * polled.
 */
export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();

  const { allowed } = await checkRateLimit("admin_qa_love_run", admin.id, { maxAttempts: 5, windowMs: 60 * 60 * 1000 });
  if (!allowed) {
    return NextResponse.json({ error: "Too many QA runs started recently — try again in a few minutes." }, { status: 429 });
  }

  const body = await request.json().catch(() => null);
  const rawCount = body?.count;
  const count = typeof rawCount === "number" && Number.isFinite(rawCount) ? Math.min(200, Math.max(10, Math.round(rawCount))) : 100;

  const result = await runLoveQaSimulation(count);

  const run = await prisma.qaSimulationRun.create({
    data: { assessmentSlug: "love", personaCount: result.personaCount, resultJson: result as any },
  });

  await logAdminAction({
    adminUserId: admin.id,
    action: "Run LOVE QA Simulation",
    entityType: "QaSimulationRun",
    entityId: run.id,
    diff: { personaCount: result.personaCount },
  });

  return NextResponse.json({ runId: run.id });
}
