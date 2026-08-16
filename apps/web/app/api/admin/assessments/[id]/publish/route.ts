import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { publishDraft } from "@/lib/admin/catalogWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  try {
    await publishDraft(id);
    await logAdminAction({ adminUserId: admin.id, action: "publish", entityType: "Assessment", entityId: id });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to publish" }, { status: 400 });
  }
}
