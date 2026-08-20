import { NextRequest, NextResponse } from "next/server";
import { renderReportPdf } from "@inner/pdf";
import { requireAdmin } from "@/lib/adminAuth";
import { buildReportPreview } from "@/lib/admin/reportPreview";

/** Renders a real PDF from synthesized sample evidence, for a "preview the actual PDF" download — never a real purchase. */
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

  const pdf = await renderReportPdf(result.document);
  return new NextResponse(new Uint8Array(pdf), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="inner-preview-${assessmentSlug}.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}
