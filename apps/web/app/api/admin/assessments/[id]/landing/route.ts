import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updateLandingContent } from "@/lib/admin/catalogWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  const input = await request.json().catch(() => null);
  if (!input) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  try {
    await updateLandingContent(id, input);
    await logAdminAction({ adminUserId: admin.id, action: "update_landing_content", entityType: "Assessment", entityId: id });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to save" }, { status: 400 });
  }
}
