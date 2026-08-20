import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { duplicatePromptTemplate } from "@/lib/admin/promptTemplatesWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;

  const created = await duplicatePromptTemplate(id, admin.id);
  await logAdminAction({ adminUserId: admin.id, action: "duplicate_prompt_template", entityType: "PromptTemplate", entityId: created.id, diff: { sourceId: id } });
  return NextResponse.json({ ok: true, id: created.id });
}
