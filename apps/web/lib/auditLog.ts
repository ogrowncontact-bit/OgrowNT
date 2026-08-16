import { prisma } from "@inner/db";

/** Every admin write goes through here — docs/ARCHITECTURE.md §10. */
export async function logAdminAction(params: {
  adminUserId: string;
  action: string;
  entityType: string;
  entityId: string;
  diff?: unknown;
}): Promise<void> {
  await prisma.auditLog.create({
    data: {
      adminUserId: params.adminUserId,
      action: params.action,
      entityType: params.entityType,
      entityId: params.entityId,
      diff: params.diff as any,
    },
  });
}
