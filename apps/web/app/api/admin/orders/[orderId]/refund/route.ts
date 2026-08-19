import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { issueRefund } from "@/lib/admin/refunds";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  const admin = await requireAdminWriter();
  const { orderId } = await params;
  const body = await request.json().catch(() => null);
  const reason = (body?.reason as string | undefined)?.trim() || undefined;
  const rawAmount = body?.amountCents;
  const amountCents = typeof rawAmount === "number" && Number.isFinite(rawAmount) && rawAmount > 0 ? Math.round(rawAmount) : undefined;

  const result = await issueRefund(orderId, reason, amountCents);
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });

  await logAdminAction({ adminUserId: admin.id, action: "refund", entityType: "Order", entityId: orderId, diff: { reason, amountCents } });
  return NextResponse.json({ ok: true });
}
