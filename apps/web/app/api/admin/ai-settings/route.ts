import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updateAiSettings } from "@/lib/aiConfig";
import { logAdminAction } from "@/lib/auditLog";

function validString(v: unknown, maxLength: number): string | null {
  return typeof v === "string" && v.trim().length > 0 && v.trim().length <= maxLength ? v.trim() : null;
}

function numberInRange(v: unknown, min: number, max: number): number | null {
  return typeof v === "number" && Number.isFinite(v) && v >= min && v <= max ? v : null;
}

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();
  const body = await request.json().catch(() => null);

  const fastModel = validString(body?.fastModel, 200);
  const qualityModel = validString(body?.qualityModel, 200);
  const temperature = numberInRange(body?.temperature, 0, 1);
  const maxTokens = numberInRange(body?.maxTokens, 1, 8192);
  const timeoutMs = numberInRange(body?.timeoutMs, 1000, 120_000);

  if (!fastModel || !qualityModel || temperature === null || maxTokens === null || timeoutMs === null) {
    return NextResponse.json(
      { error: "fastModel/qualityModel are required strings; temperature 0-1; maxTokens 1-8192; timeoutMs 1000-120000" },
      { status: 400 }
    );
  }

  const updated = await updateAiSettings({
    fastModel,
    qualityModel,
    temperature,
    maxTokens: Math.round(maxTokens),
    timeoutMs: Math.round(timeoutMs),
    updatedByAdminId: admin.id,
  });

  await logAdminAction({
    adminUserId: admin.id,
    action: "update_ai_settings",
    entityType: "AiSettings",
    entityId: "singleton",
    diff: updated,
  });

  return NextResponse.json({ ok: true, settings: updated });
}
