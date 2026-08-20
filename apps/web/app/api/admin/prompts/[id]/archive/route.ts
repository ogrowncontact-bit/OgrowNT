import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { archivePromptTemplate } from "@/lib/admin/promptTemplatesWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  const result = await archivePromptTemplate(id);
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });

  await logAdminAction({ adminUserId: admin.id, action: "archive_prompt_template", entityType: "PromptTemplate", entityId: id });
  return NextResponse.json({ ok: true });
}
