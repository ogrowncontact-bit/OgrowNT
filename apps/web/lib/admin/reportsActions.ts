import { prisma } from "@inner/db";
import { renderReportDeliveryEmail, renderReportPreparingEmail } from "@inner/email";
import { completeOrder } from "../commerce";
import { getAssessmentConfig } from "../assessments";
import { getEmailProvider } from "../email";
import { readReportPdf } from "../reportStorage";
import { recordEmailEvent } from "../emailEvents";

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/** completeOrder() is idempotent by design (see its own docstring) — an admin retry is just calling it again. */
export async function retryReportGeneration(reportId: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const report = await prisma.report.findUnique({
    where: { id: reportId },
    include: { order: { include: { user: true, price: { include: { assessment: true } } } }, assessmentSession: true },
  });
  if (!report) return { ok: false, error: "Report not found" };

  // Only a report that already failed once is a "taking longer than usual"
  // case worth a reassurance email — the normal first-attempt path already
  // gets the purchase-confirmation email from completeOrder() itself.
  if (report.status === "failed") {
    const statusUrl = `${appBaseUrl()}/${report.assessmentSession.sourceSlug}/session/${report.assessmentSessionId}/report`;
    const sendResult = await getEmailProvider().send({
      to: report.order.user.email,
      subject: `${report.order.price.assessment.name} — still preparing your report`,
      html: renderReportPreparingEmail({ assessmentName: report.order.price.assessment.name, statusUrl }),
    });
    await recordEmailEvent({
      userId: report.order.userId,
      type: "report_preparing",
      templateKey: "report_preparing_v1",
      providerRef: sendResult.providerRef,
      relatedEntityId: report.id,
      status: sendResult.ok ? "sent" : "failed",
    });
  }

  try {
    await completeOrder(report.orderId);
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Retry failed" };
  }
}

/** Re-sends the already-generated PDF without regenerating it — for a report stuck at emailStatus "failed". */
export async function retryReportEmail(reportId: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const report = await prisma.report.findUnique({
    where: { id: reportId },
    include: { order: { include: { user: true, price: { include: { assessment: true } } } }, assessmentSession: true },
  });
  if (!report) return { ok: false, error: "Report not found" };
  if (report.status !== "ready" || !report.pdfObjectKey) return { ok: false, error: "Report isn't ready to send yet" };

  const [profileResult, config] = await Promise.all([
    prisma.profileResult.findUnique({ where: { assessmentSessionId: report.assessmentSessionId } }),
    getAssessmentConfig(report.assessmentSession.sourceSlug),
  ]);
  const profileName =
    config?.profiles.find((p) => p.key === profileResult?.primaryProfileKey)?.name ?? report.order.price.assessment.name;
  const reportViewUrl = `${appBaseUrl()}/${report.assessmentSession.sourceSlug}/session/${report.assessmentSessionId}/report`;

  const pdf = await readReportPdf(report.pdfObjectKey);
  const sendResult = await getEmailProvider().send({
    to: report.order.user.email,
    subject: `${report.order.price.assessment.name} — your report is ready`,
    html: renderReportDeliveryEmail({ assessmentName: report.order.price.assessment.name, profileName, reportViewUrl }),
    attachments: [{ filename: "inner-report.pdf", content: pdf, contentType: "application/pdf" }],
  });
  await recordEmailEvent({
    userId: report.order.userId,
    type: "report_delivery",
    templateKey: "report_delivery_v1",
    providerRef: sendResult.providerRef,
    relatedEntityId: report.id,
    status: sendResult.ok ? "sent" : "failed",
  });
  if (!sendResult.ok) return { ok: false, error: "Email provider failed to send" };

  await prisma.report.update({ where: { id: report.id }, data: { deliveredAt: new Date() } });
  return { ok: true };
}
