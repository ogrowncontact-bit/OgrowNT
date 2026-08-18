import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { retryReportEmail } from "@/lib/admin/reportsActions";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ reportId: string }> }) {
  const admin = await requireAdminWriter();
  const { reportId } = await params;

  const result = await retryReportEmail(reportId);
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });

  await logAdminAction({ adminUserId: admin.id, action: "retry_report_email", entityType: "Report", entityId: reportId });
  return NextResponse.json({ ok: true });
}
