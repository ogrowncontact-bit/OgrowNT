import { prisma, Prisma } from "@inner/db";
import { generateReport, type ReportContext, type ReportTension } from "@inner/ai";
import { renderReportPdf } from "@inner/pdf";
import { renderReportDeliveryEmail } from "@inner/email";
import { dimensionPool } from "@inner/content/dimensions";
import { getAssessmentConfig } from "./assessments";
import { getEmailProvider } from "./email";
import { storeReportPdf } from "./reportStorage";
import { track } from "./analytics";
import type { OpenResponseAiMeta } from "./openResponseAiMeta";
import { ensureAiTelemetryRegistered } from "./aiTelemetry";

// See the comment in app/api/sessions/[id]/answer/route.ts — registered per
// module realm, not just once globally via instrumentation.ts.
ensureAiTelemetryRegistered();

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/**
 * The one place that turns a paid order into a delivered report — called
 * from both the real Stripe webhook and the dev mock-payment route, so
 * they exercise identical downstream logic (§ commerce flow). Idempotent:
 * safe to call twice for the same order (webhook redelivery, a retried
 * mock click, or an admin-triggered retry after a prior failure) — a
 * Report row is looked up by Order (now unique) *before* spending an AI
 * call, PDF render, or email send, not just de-duplicated after the fact
 * via a database constraint on the entitlement.
 */
export async function completeOrder(orderId: string): Promise<void> {
  const order = await prisma.order.findUnique({ where: { id: orderId }, include: { assessmentSession: true } });
  if (!order) throw new Error(`Order ${orderId} not found`);
  if (order.status === "paid") return;

  const session = order.assessmentSession;
  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) throw new Error(`Unknown assessment for order ${orderId}`);

  const existingReport = await prisma.report.findUnique({ where: { orderId: order.id } });
  if (existingReport && existingReport.status !== "failed") {
    // Already generated (or another call is mid-flight) — never regenerate a
    // paid report unnecessarily. Just make sure downstream state agrees.
    await prisma.entitlement.upsert({
      where: { orderId: order.id },
      update: {},
      create: { userId: order.userId, assessmentSessionId: session.id, orderId: order.id, reportId: existingReport.id },
    });
    await prisma.order.update({ where: { id: order.id }, data: { status: "paid", paidAt: new Date() } });
    return;
  }

  const [profileResultRow, dimensionScoreRows, openResponses, user] = await Promise.all([
    prisma.profileResult.findUnique({ where: { assessmentSessionId: session.id } }),
    prisma.dimensionScore.findMany({ where: { assessmentSessionId: session.id } }),
    prisma.openResponse.findMany({ where: { assessmentSessionId: session.id } }),
    prisma.user.findUniqueOrThrow({ where: { id: order.userId } }),
  ]);
  if (!profileResultRow) throw new Error(`Session ${session.id} has no profile result yet`);

  const primary = config.profiles.find((p) => p.key === profileResultRow.primaryProfileKey);
  if (!primary) throw new Error(`Unknown profile key ${profileResultRow.primaryProfileKey}`);
  const secondaryKeys = (profileResultRow.secondaryProfileKeys as string[]) ?? [];
  const secondaryProfiles = config.profiles.filter((p) => secondaryKeys.includes(p.key));
  const dimensionScores = Object.fromEntries(dimensionScoreRows.map((d) => [d.dimensionKey, d.normalizedScore]));
  const dimensionConfidence = Object.fromEntries(dimensionScoreRows.map((d) => [d.dimensionKey, d.confidence]));
  const openAnswerTags = openResponses.flatMap((r) => (r.aiTags as OpenResponseAiMeta | null)?.tags ?? []);
  const tensions: ReportTension[] = ((profileResultRow.tensions as { label: string; strength: number }[] | null) ?? []).map((t) => ({
    label: t.label,
    strength: t.strength,
  }));

  await track({ anonymousSessionId: session.anonymousSessionId, eventName: "report_generation_started", assessmentId: session.assessmentId });

  try {
    const reportContext: ReportContext = {
      assessmentName: config.name,
      assessmentVersion: config.version,
      primaryProfileName: primary.name,
      primaryProfileDescription: primary.descriptionTemplate,
      secondaryProfileNames: secondaryProfiles.map((p) => p.name),
      dimensionScores,
      dimensionConfidence,
      dimensionLabels,
      tensions,
      openAnswerThemes: openAnswerTags,
      language: order.language,
      reportType: "individual",
      sections: config.premiumReportStructure.map((s) => ({ key: s.key, title: s.title })),
    };

    const generated = await generateReport(reportContext);

    const pdf = await renderReportPdf({
      assessmentName: config.name,
      profileName: primary.name,
      profileDescription: primary.descriptionTemplate,
      sections: generated.sections,
      dimensionScores: Object.entries(dimensionScores).map(([key, normalized]) => ({
        key,
        label: dimensionLabels[key] ?? key,
        normalized,
      })),
      generatedAt: new Date(),
    });

    const report = await prisma.report.upsert({
      where: { orderId: order.id },
      update: {
        status: "ready",
        content: { sections: generated.sections, generatedAt: new Date().toISOString() } as any,
        language: generated.language,
        reportEngineVersion: generated.reportEngineVersion,
        promptVersion: generated.promptVersion,
        modelVersion: generated.modelVersion,
        failureReason: null,
      },
      create: {
        assessmentSessionId: session.id,
        orderId: order.id,
        templateVersion: 1,
        status: "ready",
        content: { sections: generated.sections, generatedAt: new Date().toISOString() } as any,
        language: generated.language,
        reportEngineVersion: generated.reportEngineVersion,
        promptVersion: generated.promptVersion,
        modelVersion: generated.modelVersion,
      },
    });

    const objectKey = await storeReportPdf(report.id, pdf);
    const reportViewUrl = `${appBaseUrl()}/${session.sourceSlug}/session/${session.id}/report`;

    const emailProvider = getEmailProvider();
    const sendResult = await emailProvider.send({
      to: user.email,
      subject: `${config.name} — your report is ready`,
      html: renderReportDeliveryEmail({ assessmentName: config.name, profileName: primary.name, reportViewUrl }),
      attachments: [{ filename: "inner-report.pdf", content: pdf, contentType: "application/pdf" }],
    });

    try {
      await prisma.$transaction([
        prisma.report.update({
          where: { id: report.id },
          data: { pdfObjectKey: objectKey, deliveredAt: sendResult.ok ? new Date() : null },
        }),
        prisma.order.update({ where: { id: order.id }, data: { status: "paid", paidAt: new Date() } }),
        prisma.entitlement.upsert({
          where: { orderId: order.id },
          update: { reportId: report.id },
          create: { userId: order.userId, assessmentSessionId: session.id, orderId: order.id, reportId: report.id },
        }),
      ]);
    } catch (error) {
      // A concurrent call for the same order (a double-click, a retried mock
      // click, or Stripe's documented at-least-once webhook redelivery) can
      // race past the existing-report guard above before either has
      // committed the report row. Entitlement.orderId is unique, so the
      // loser hits P2002 here — that's the other call having already
      // finished the job, not a real failure.
      const isDuplicateEntitlement = error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2002";
      if (!isDuplicateEntitlement) throw error;
      return;
    }

    await track({ anonymousSessionId: session.anonymousSessionId, eventName: "payment_completed", assessmentId: session.assessmentId });
    await track({ anonymousSessionId: session.anonymousSessionId, eventName: "report_generated", assessmentId: session.assessmentId });
    if (sendResult.ok) {
      await track({ anonymousSessionId: session.anonymousSessionId, eventName: "report_delivered", assessmentId: session.assessmentId });
    } else {
      await track({ anonymousSessionId: session.anonymousSessionId, eventName: "report_email_failed", assessmentId: session.assessmentId });
    }
  } catch (error) {
    // Payment already succeeded by the time this runs (this function is only
    // ever called after provider confirmation) — a failure here must never
    // look like a failed purchase. Keep a durable, retryable failure record
    // instead of losing the report entirely; the order stays "pending" so
    // the paywall/report page keeps showing the "being created" state
    // rather than granting access to nothing.
    const reason = error instanceof Error ? error.message : "Unknown report generation error";
    await prisma.report.upsert({
      where: { orderId: order.id },
      update: { status: "failed", failureReason: reason },
      create: { assessmentSessionId: session.id, orderId: order.id, templateVersion: 1, status: "failed", failureReason: reason, content: Prisma.JsonNull },
    });
    await track({ anonymousSessionId: session.anonymousSessionId, eventName: "report_generation_failed", assessmentId: session.assessmentId });
    throw error;
  }
}
