import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { createJournalPost } from "@/lib/admin/journalWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();
  const body = await request.json().catch(() => null);
  if (!body) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  try {
    const { id } = await createJournalPost(body);
    await logAdminAction({ adminUserId: admin.id, action: "create_journal_post", entityType: "JournalPost", entityId: id });
    return NextResponse.json({ id });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to create" }, { status: 400 });
  }
}
