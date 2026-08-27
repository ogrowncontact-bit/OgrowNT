import { NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { requireAdminWriter } from "@/lib/adminAuth";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ ticketId: string }> }) {
  const admin = await requireAdminWriter();
  const { ticketId } = await params;

  const ticket = await prisma.supportTicket.update({ where: { id: ticketId }, data: { status: "resolved" } });

  await logAdminAction({
    adminUserId: admin.id,
    action: "resolve_support_ticket",
    entityType: "SupportTicket",
    entityId: ticketId,
    diff: { status: ticket.status },
  });

  return NextResponse.json({ ok: true });
}
