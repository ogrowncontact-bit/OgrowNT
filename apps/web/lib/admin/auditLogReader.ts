import { prisma } from "@inner/db";

export interface AuditLogRow {
  id: string;
  adminEmail: string;
  action: string;
  entityType: string;
  entityId: string;
  createdAt: Date;
}

/** Every admin mutation already writes here via lib/auditLog.ts's logAdminAction — this is the first read UI for it. */
export async function listAuditLog(limit = 200): Promise<AuditLogRow[]> {
  const rows = await prisma.auditLog.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: { adminUser: { select: { email: true } } },
  });
  return rows.map((r) => ({
    id: r.id,
    adminEmail: r.adminUser.email,
    action: r.action,
    entityType: r.entityType,
    entityId: r.entityId,
    createdAt: r.createdAt,
  }));
}
