import { prisma } from "@inner/db";

export interface AdminEmailRow {
  id: string;
  email: string;
  type: string;
  templateKey: string;
  transactional: boolean;
  status: string;
  failureReason: string | null;
  sentAt: Date;
  deliveredAt: Date | null;
  bouncedAt: Date | null;
  openedAt: Date | null;
  clickedAt: Date | null;
  /** Report.id — only meaningful for report_delivery/report_preparing, the one type with a wired-up retry action today. */
  reportId: string | null;
}

/** Newest first — mirrors /admin/orders and /admin/reports conventions. */
export async function listEmailEventsForAdmin(limit = 100): Promise<AdminEmailRow[]> {
  const events = await prisma.emailEvent.findMany({
    orderBy: { sentAt: "desc" },
    take: limit,
    include: { user: true },
  });

  return events.map((e) => ({
    id: e.id,
    email: e.user.email,
    type: e.type,
    templateKey: e.templateKey,
    transactional: e.transactional,
    status: e.status,
    failureReason: e.failureReason,
    sentAt: e.sentAt,
    deliveredAt: e.deliveredAt,
    bouncedAt: e.bouncedAt,
    openedAt: e.openedAt,
    clickedAt: e.clickedAt,
    reportId: e.type === "report_delivery" || e.type === "report_preparing" ? e.relatedEntityId : null,
  }));
}

export interface EmailStatusCounts {
  sent: number;
  delivered: number;
  bounced: number;
  failed: number;
}

export async function getEmailStatusCounts(): Promise<EmailStatusCounts> {
  const [sent, delivered, bounced, failed] = await Promise.all([
    prisma.emailEvent.count({ where: { status: "sent" } }),
    prisma.emailEvent.count({ where: { status: "delivered" } }),
    prisma.emailEvent.count({ where: { status: "bounced" } }),
    prisma.emailEvent.count({ where: { status: "failed" } }),
  ]);
  return { sent, delivered, bounced, failed };
}
