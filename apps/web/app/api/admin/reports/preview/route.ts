import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/adminAuth";
import { buildReportPreview } from "@/lib/admin/reportPreview";

/** Read-only preview for any admin role — never touches a real purchase or a real user's data. */
export async function POST(request: NextRequest) {
  await requireAdmin();
  const body = await request.json().catch(() => null);

  const assessmentSlug = typeof body?.assessmentSlug === "string" ? body.assessmentSlug : null;
  if (!assessmentSlug) return NextResponse.json({ error: "assessmentSlug is required" }, { status: 400 });

  const result = await buildReportPreview({
    assessmentSlug,
    sampleProfileKey: typeof body?.sampleProfileKey === "string" ? body.sampleProfileKey : undefined,
    language: typeof body?.language === "string" ? body.language : undefined,
  });

  if ("error" in result) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json(result);
}
