import { NextRequest, NextResponse } from "next/server";
import { validateAssessmentConfig } from "@inner/content";
import { requireAdminWriter } from "@/lib/adminAuth";
import { saveAssessmentDraft } from "@/lib/admin/catalogWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  const config = await request.json().catch(() => null);
  if (!config) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  const violations = validateAssessmentConfig(config);
  if (violations.length > 0) {
    return NextResponse.json({ error: "Validation failed", violations }, { status: 422 });
  }

  try {
    const { versionId } = await saveAssessmentDraft(id, config);
    await logAdminAction({ adminUserId: admin.id, action: "save_draft", entityType: "AssessmentVersion", entityId: versionId });
    return NextResponse.json({ ok: true, versionId });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to save draft" }, { status: 400 });
  }
}
