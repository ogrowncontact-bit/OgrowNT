import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { createAssessment } from "@/lib/admin/catalogWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();

  const body = await request.json().catch(() => null);
  const { slug, name, category, hook, description, targetAudience } = body ?? {};
  if (!slug || !name || !category || !hook || !description || !targetAudience) {
    return NextResponse.json({ error: "All fields are required" }, { status: 400 });
  }

  try {
    const { id } = await createAssessment({ slug, name, category, hook, description, targetAudience });
    await logAdminAction({ adminUserId: admin.id, action: "create", entityType: "Assessment", entityId: id, diff: body });
    return NextResponse.json({ id });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to create assessment" }, { status: 400 });
  }
}
