import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updatePromptTemplate } from "@/lib/admin/promptTemplatesWriter";
import { logAdminAction } from "@/lib/auditLog";

function validString(v: unknown, maxLength: number): string | null {
  return typeof v === "string" && v.trim().length > 0 && v.trim().length <= maxLength ? v.trim() : null;
}

function toneOrDefault(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.5;
}

/** Edits a draft/testing prompt's content in place. Published/archived rows are rejected by the writer — duplicate first. */
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  const body = await request.json().catch(() => null);

  const personaName = validString(body?.personaName, 100);
  const personaFocus = validString(body?.personaFocus, 300);
  const personaPrompt = validString(body?.personaPrompt, 4000);
  if (!personaName || !personaFocus || !personaPrompt) {
    return NextResponse.json({ error: "personaName, personaFocus, and personaPrompt are required" }, { status: 400 });
  }

  const result = await updatePromptTemplate(id, {
    personaName,
    personaFocus,
    personaPrompt,
    toneWarmth: toneOrDefault(body?.toneWarmth),
    toneDirectness: toneOrDefault(body?.toneDirectness),
    toneDepth: toneOrDefault(body?.toneDepth),
    toneFormality: toneOrDefault(body?.toneFormality),
  });
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });

  await logAdminAction({ adminUserId: admin.id, action: "update_prompt_template", entityType: "PromptTemplate", entityId: id });
  return NextResponse.json({ ok: true });
}
