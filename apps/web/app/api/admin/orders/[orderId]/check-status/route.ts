import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { checkOrderPaymentStatus } from "@/lib/admin/orderReconciliation";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  const admin = await requireAdminWriter();
  const { orderId } = await params;

  const result = await checkOrderPaymentStatus(orderId);
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });

  await logAdminAction({ adminUserId: admin.id, action: "check_payment_status", entityType: "Order", entityId: orderId, diff: { status: result.status } });
  return NextResponse.json({ ok: true, status: result.status });
}
