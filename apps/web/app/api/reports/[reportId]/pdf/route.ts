import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readReportPdf } from "@/lib/reportStorage";

/** Ownership-checked PDF download — stands in for a short-lived signed R2 URL until real object storage is wired (see lib/reportStorage.ts). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ reportId: string }> }) {
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const { reportId } = await params;
  const report = await prisma.report.findUnique({ where: { id: reportId }, include: { assessmentSession: true } });
  if (!report || report.assessmentSession.anonymousSessionId !== anonymousSessionId || !report.pdfObjectKey) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const pdf = await readReportPdf(report.pdfObjectKey);
  return new NextResponse(new Uint8Array(pdf), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="inner-report.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}
