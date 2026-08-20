import { NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { publishJournalPost } from "@/lib/admin/journalWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  try {
    await publishJournalPost(id);
    await logAdminAction({ adminUserId: admin.id, action: "publish_journal_post", entityType: "JournalPost", entityId: id });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to publish" }, { status: 400 });
  }
}
