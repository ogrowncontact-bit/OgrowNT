import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updateCampaign, setCampaignStatus } from "@/lib/admin/campaignsWriter";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdminWriter();
  const { id } = await params;
  const body = await request.json().catch(() => null);
  if (!body) return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });

  try {
    if (body.status) {
      await setCampaignStatus(id, body.status);
      await logAdminAction({ adminUserId: admin.id, action: "set_campaign_status", entityType: "Campaign", entityId: id, diff: { status: body.status } });
    } else {
      await updateCampaign(id, body);
      await logAdminAction({ adminUserId: admin.id, action: "update_campaign", entityType: "Campaign", entityId: id });
    }
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Failed to save" }, { status: 400 });
  }
}
