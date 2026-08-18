import { prisma } from "@inner/db";

export interface AdminUserRow {
  id: string;
  email: string;
  createdAt: Date;
  assessmentsCompleted: number;
  purchases: number;
  marketingConsent: boolean | null;
  lastActivity: Date | null;
}

/**
 * Minimal fields only, per the spec's own privacy guidance — never surfaces
 * assessment answers, profile results, or report content here. Newest
 * first: an operator checking in on the platform cares most about who just
 * showed up.
 */
export async function listUsersForAdmin(limit = 100): Promise<AdminUserRow[]> {
  const users = await prisma.user.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: {
      anonymousSessions: {
        select: { lastSeenAt: true, assessmentSessions: { where: { status: "completed" }, select: { id: true } } },
      },
      orders: { where: { status: "paid" }, select: { id: true } },
      marketingConsents: { orderBy: { consentTimestamp: "desc" }, take: 1, select: { consent: true } },
    },
  });

  return users.map((u) => {
    const lastActivity = u.anonymousSessions.reduce<Date | null>((latest, s) => {
      if (!latest || s.lastSeenAt > latest) return s.lastSeenAt;
      return latest;
    }, null);

    return {
      id: u.id,
      email: u.email,
      createdAt: u.createdAt,
      assessmentsCompleted: u.anonymousSessions.reduce((sum, s) => sum + s.assessmentSessions.length, 0),
      purchases: u.orders.length,
      marketingConsent: u.marketingConsents[0]?.consent ?? null,
      lastActivity,
    };
  });
}
