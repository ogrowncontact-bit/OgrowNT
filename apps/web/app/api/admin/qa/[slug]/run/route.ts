import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { requireAdminWriter } from "@/lib/adminAuth";
import { checkRateLimit } from "@/lib/security/rateLimit";
import { logAdminAction } from "@/lib/auditLog";
import { getAssessmentConfig } from "@/lib/assessments";
import { runLoveQaSimulation } from "@/lib/qa/runLoveQaSimulation";
import { runAssessmentQaSimulation } from "@/lib/qa/runAssessmentQaSimulation";

/**
 * FASE 31 §100-PERSONA QA SIMULATION, generalized — admin-gated trigger for
 * any assessment slug (originally /admin/qa/love/run only). Runs ~100
 * synthetic sessions through the real engine and persists the aggregate
 * result so /admin/qa/[slug] can render it without re-running on every page
 * view. Rate-limited: each run does real DB work across ~100 sessions and is
 * meant to be triggered deliberately, not polled.
 *
 * slug "love" is routed through the original runLoveQaSimulation.ts
 * untouched, so LOVE's QA history stays byte-for-byte comparable to earlier
 * runs; every other slug goes through the generic
 * lib/qa/runAssessmentQaSimulation.ts.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const admin = await requireAdminWriter();

  const config = await getAssessmentConfig(slug);
  if (!config) {
    return NextResponse.json({ error: `Assessment "${slug}" is not available` }, { status: 404 });
  }

  const { allowed } = await checkRateLimit(`admin_qa_${slug}_run`, admin.id, { maxAttempts: 5, windowMs: 60 * 60 * 1000 });
  if (!allowed) {
    return NextResponse.json({ error: "Too many QA runs started recently — try again in a few minutes." }, { status: 429 });
  }

  const body = await request.json().catch(() => null);
  const rawCount = body?.count;
  const count = typeof rawCount === "number" && Number.isFinite(rawCount) ? Math.min(200, Math.max(10, Math.round(rawCount))) : 100;

  const result = slug === "love" ? await runLoveQaSimulation(count) : await runAssessmentQaSimulation(slug, count);

  const run = await prisma.qaSimulationRun.create({
    data: { assessmentSlug: slug, personaCount: result.personaCount, resultJson: result as any },
  });

  await logAdminAction({
    adminUserId: admin.id,
    action: `Run ${config.name} QA Simulation`,
    entityType: "QaSimulationRun",
    entityId: run.id,
    diff: { personaCount: result.personaCount },
  });

  return NextResponse.json({ runId: run.id });
}
