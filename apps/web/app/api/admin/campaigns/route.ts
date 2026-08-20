import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { createCampaign } from "@/lib/admin/campaignsWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();
  const body = await request.json().catch(() => null);
  if (!body) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  try {
    const { id } = await createCampaign(body);
    await logAdminAction({ adminUserId: admin.id, action: "create_campaign", entityType: "Campaign", entityId: id });
    return NextResponse.json({ id });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to create" }, { status: 400 });
  }
}
