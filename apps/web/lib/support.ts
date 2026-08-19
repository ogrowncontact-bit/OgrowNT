import { prisma } from "@inner/db";
import { renderReportDeliveryEmail } from "@inner/email";
import { getAssessmentConfig } from "./assessments";
import { getEmailProvider } from "./email";
import { readReportPdf } from "./reportStorage";
import { recordEmailEvent } from "./emailEvents";

const RESEND_COOLDOWN_MS = 10 * 60 * 1000;

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/**
 * "I didn't receive my report" self-serve — always resolves the same way
 * whether or not the email is on file, same reasoning as lib/privacy.ts.
 * Resends the most recent purchased report only; someone with several
 * purchases can request again for an older one isn't supported yet (a
 * reasonable v1 scope call, not an oversight).
 */
export async function resendMostRecentReport(email: string): Promise<void> {
  const user = await prisma.user.findUnique({ where: { email: email.trim().toLowerCase() } });
  if (!user) return;

  // No status filter: a Report row only ever exists for an order that
  // completed successfully, and a refund reverses the charge, not the
  // delivery (see lib/admin/refunds.ts) — so a refunded order's report is
  // still fair to resend.
  const report = await prisma.report.findFirst({
    where: { order: { userId: user.id } },
    orderBy: { generatedAt: "desc" },
    include: { order: { include: { price: { include: { assessment: true } } } }, assessmentSession: true },
  });
  if (!report || !report.pdfObjectKey) return;

  const recentResend = await prisma.emailEvent.findFirst({
    where: { userId: user.id, type: "report_resend", sentAt: { gt: new Date(Date.now() - RESEND_COOLDOWN_MS) } },
  });
  if (recentResend) return;

  const [profileResult, config] = await Promise.all([
    prisma.profileResult.findUnique({ where: { assessmentSessionId: report.assessmentSessionId } }),
    getAssessmentConfig(report.assessmentSession.sourceSlug),
  ]);
  const profileName =
    config?.profiles.find((p) => p.key === profileResult?.primaryProfileKey)?.name ?? report.order.price.assessment.name;

  const pdf = await readReportPdf(report.pdfObjectKey);
  const reportViewUrl = `${appBaseUrl()}/${report.assessmentSession.sourceSlug}/session/${report.assessmentSessionId}/report`;

  const sendResult = await getEmailProvider().send({
    to: user.email,
    subject: `${report.order.price.assessment.name} — your report, resent`,
    html: renderReportDeliveryEmail({ assessmentName: report.order.price.assessment.name, profileName, reportViewUrl }),
    attachments: [{ filename: "inner-report.pdf", content: pdf, contentType: "application/pdf" }],
  });

  await recordEmailEvent({
    userId: user.id,
    type: "report_resend",
    templateKey: "report_delivery_v1",
    providerRef: sendResult.providerRef,
    relatedEntityId: report.id,
    status: sendResult.ok ? "sent" : "failed",
  });
}
