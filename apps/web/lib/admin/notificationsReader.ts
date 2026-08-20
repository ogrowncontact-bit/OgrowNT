import { prisma } from "@inner/db";

export interface OperationalAlert {
  severity: "warning" | "critical";
  message: string;
  href: string;
}

/**
 * Derived entirely from data that already exists — no new event system,
 * no fabricated "webhook issue" placeholder. Only surfaces a condition
 * when the real count backing it is actually nonzero.
 */
export async function getOperationalAlerts(): Promise<OperationalAlert[]> {
  const [reportsFailed, emailsFailed, pendingOrdersStuck] = await Promise.all([
    prisma.report.count({ where: { status: "failed" } }),
    prisma.report.count({ where: { status: "ready", deliveredAt: null } }),
    // "Stuck" pending — created over an hour ago with no payment resolution yet.
    prisma.order.count({ where: { status: "pending", createdAt: { lt: new Date(Date.now() - 60 * 60 * 1000) } } }),
  ]);

  const alerts: OperationalAlert[] = [];
  if (reportsFailed > 0) {
    alerts.push({
      severity: "critical",
      message: `${reportsFailed} report${reportsFailed === 1 ? "" : "s"} failed to generate`,
      href: "/admin/reports",
    });
  }
  if (emailsFailed > 0) {
    alerts.push({
      severity: "warning",
      message: `${emailsFailed} report email${emailsFailed === 1 ? "" : "s"} not yet delivered`,
      href: "/admin/reports",
    });
  }
  if (pendingOrdersStuck > 0) {
    alerts.push({
      severity: "warning",
      message: `${pendingOrdersStuck} order${pendingOrdersStuck === 1 ? "" : "s"} stuck pending for over an hour`,
      href: "/admin/orders",
    });
  }
  return alerts;
}
