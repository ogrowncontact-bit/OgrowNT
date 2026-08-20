import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { unpublishJournalPost } from "@/lib/admin/journalWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  await unpublishJournalPost(id);
  await logAdminAction({ adminUserId: admin.id, action: "unpublish_journal_post", entityType: "JournalPost", entityId: id });
  return NextResponse.json({ ok: true });
}
