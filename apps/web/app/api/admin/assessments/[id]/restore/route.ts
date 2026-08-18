import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { restoreAssessment } from "@/lib/admin/catalogWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  try {
    await restoreAssessment(id);
    await logAdminAction({ adminUserId: admin.id, action: "restore", entityType: "Assessment", entityId: id });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to restore" }, { status: 400 });
  }
}
