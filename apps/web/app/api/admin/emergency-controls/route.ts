import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { updateEmergencyControls } from "@/lib/emergencyControls";
import { logAdminAction } from "@/lib/auditLog";

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();
  const body = await request.json().catch(() => null);

  const purchasesPaused = body?.purchasesPaused === true;
  const reportGenerationPaused = body?.reportGenerationPaused === true;
  const aiForceFallback = body?.aiForceFallback === true;

  const updated = await updateEmergencyControls({
    purchasesPaused,
    reportGenerationPaused,
    aiForceFallback,
    updatedByAdminId: admin.id,
  });

  await logAdminAction({
    adminUserId: admin.id,
    action: "update_emergency_controls",
    entityType: "FeatureFlags",
    entityId: "singleton",
    diff: updated,
  });

  return NextResponse.json({ ok: true, controls: updated });
}
