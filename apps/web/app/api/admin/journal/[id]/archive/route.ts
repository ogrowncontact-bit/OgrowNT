import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { archiveJournalPost } from "@/lib/admin/journalWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  await archiveJournalPost(id);
  await logAdminAction({ adminUserId: admin.id, action: "archive_journal_post", entityType: "JournalPost", entityId: id });
  return NextResponse.json({ ok: true });
}
