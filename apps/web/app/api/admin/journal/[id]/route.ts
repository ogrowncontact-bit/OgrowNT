import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updateJournalPost } from "@/lib/admin/journalWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  const body = await request.json().catch(() => null);
  if (!body) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  try {
    await updateJournalPost(id, body);
    await logAdminAction({ adminUserId: admin.id, action: "update_journal_post", entityType: "JournalPost", entityId: id });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to save" }, { status: 400 });
  }
}
