import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { createPromptTemplate } from "@/lib/admin/promptTemplatesWriter";
import { logAdminAction } from "@/lib/auditLog";

function validString(v: unknown, maxLength: number): string | null {
  return typeof v === "string" && v.trim().length > 0 && v.trim().length <= maxLength ? v.trim() : null;
}

function toneOrDefault(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.5;
}

/** Creates a brand-new draft persona for an assessment that has none yet. */
export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();
  const body = await request.json().catch(() => null);

  const assessmentSlug = validString(body?.assessmentSlug, 100);
  const personaName = validString(body?.personaName, 100);
  const personaFocus = validString(body?.personaFocus, 300);
  const personaPrompt = validString(body?.personaPrompt, 4000);
  if (!assessmentSlug || !personaName || !personaFocus || !personaPrompt) {
    return NextResponse.json({ error: "assessmentSlug, personaName, personaFocus, and personaPrompt are required" }, { status: 400 });
  }

  const created = await createPromptTemplate(
    assessmentSlug,
    {
      personaName,
      personaFocus,
      personaPrompt,
      toneWarmth: toneOrDefault(body?.toneWarmth),
      toneDirectness: toneOrDefault(body?.toneDirectness),
      toneDepth: toneOrDefault(body?.toneDepth),
      toneFormality: toneOrDefault(body?.toneFormality),
    },
    admin.id
  );

  await logAdminAction({ adminUserId: admin.id, action: "create_prompt_template", entityType: "PromptTemplate", entityId: created.id, diff: { assessmentSlug, version: created.version } });
  return NextResponse.json({ ok: true, id: created.id });
}
