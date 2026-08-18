import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { readAccessUserId } from "@/lib/access";
import { readReportPdf } from "@/lib/reportStorage";
import { track } from "@/lib/analytics";

/** Ownership-checked PDF download — stands in for a short-lived signed R2 URL until real object storage is wired (see lib/reportStorage.ts). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ reportId: string }> }) {
  const anonymousSessionId = await readAnonymousSessionId();
  const accessUserId = await readAccessUserId();
  if (!anonymousSessionId && !accessUserId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const { reportId } = await params;
  const report = await prisma.report.findUnique({
    where: { id: reportId },
    include: { assessmentSession: { include: { anonymousSession: true } } },
  });
  if (!report || !report.pdfObjectKey) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const ownsViaCurrentSession = anonymousSessionId !== null && report.assessmentSession.anonymousSessionId === anonymousSessionId;
  const ownsViaMagicLink = accessUserId !== null && report.assessmentSession.anonymousSession.userId === accessUserId;
  if (!ownsViaCurrentSession && !ownsViaMagicLink) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  await track({
    anonymousSessionId: report.assessmentSession.anonymousSessionId,
    eventName: "pdf_downloaded",
    assessmentId: report.assessmentSession.assessmentId,
    properties: { reportId: report.id },
  });

  const pdf = await readReportPdf(report.pdfObjectKey);
  return new NextResponse(new Uint8Array(pdf), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="inner-report.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}
