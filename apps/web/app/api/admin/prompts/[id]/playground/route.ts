import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/adminAuth";
import { runPromptPlayground } from "@/lib/admin/promptPlayground";

/** Read-only (any admin role, including viewer, can run the playground — it never mutates a prompt). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  await requireAdmin();
  const { id } = await params;
  const body = await request.json().catch(() => null);

  const result = await runPromptPlayground({
    promptTemplateId: id,
    sampleProfileKey: typeof body?.sampleProfileKey === "string" ? body.sampleProfileKey : undefined,
    sampleThemes: typeof body?.sampleThemes === "string" ? body.sampleThemes : undefined,
    language: typeof body?.language === "string" ? body.language : undefined,
  });

  if ("error" in result) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json(result);
}
