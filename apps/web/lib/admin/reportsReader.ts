import { prisma } from "@inner/db";

export interface AdminReportRow {
  id: string;
  orderId: string;
  assessmentName: string;
  assessmentSlug: string;
  email: string;
  language: string;
  status: string;
  generatedAt: Date;
  hasPdf: boolean;
  emailStatus: "delivered" | "failed" | "n/a";
  failureReason: string | null;
}

/** Newest first — an operator triaging failures wants the most recent ones on top. */
export async function listReportsForAdmin(limit = 100): Promise<AdminReportRow[]> {
  const reports = await prisma.report.findMany({
    orderBy: { generatedAt: "desc" },
    take: limit,
    include: { order: { include: { user: true, price: { include: { assessment: true } } } } },
  });

  return reports.map((r) => ({
    id: r.id,
    orderId: r.orderId,
    assessmentName: r.order.price.assessment.name,
    assessmentSlug: r.order.price.assessment.slug,
    email: r.order.user.email,
    language: r.language,
    status: r.status,
    generatedAt: r.generatedAt,
    hasPdf: !!r.pdfObjectKey,
    // Report.deliveredAt is only ever set on a successful send (see
    // lib/commerce.ts) — null on a "ready" report means the original send
    // failed, since generation can't reach "ready" without attempting it.
    emailStatus: r.status !== "ready" ? "n/a" : r.deliveredAt ? "delivered" : "failed",
    failureReason: r.failureReason,
  }));
}

export interface ReportStatusCounts {
  ready: number;
  generating: number;
  pending: number;
  failed: number;
  emailFailed: number;
}

export async function getReportStatusCounts(): Promise<ReportStatusCounts> {
  const [ready, generating, pending, failed, emailFailed] = await Promise.all([
    prisma.report.count({ where: { status: "ready" } }),
    prisma.report.count({ where: { status: "generating" } }),
    prisma.report.count({ where: { status: "pending" } }),
    prisma.report.count({ where: { status: "failed" } }),
    prisma.report.count({ where: { status: "ready", deliveredAt: null } }),
  ]);
  return { ready, generating, pending, failed, emailFailed };
}
