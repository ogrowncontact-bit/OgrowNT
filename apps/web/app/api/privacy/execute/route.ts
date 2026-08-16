import { NextRequest, NextResponse } from "next/server";
import { buildExport, executeDeletion, verifyPrivacyToken } from "@/lib/privacy";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const payload = verifyPrivacyToken(body?.token as string | undefined);
  if (!payload) {
    return NextResponse.json({ error: "This link has expired or is invalid. Request a new one." }, { status: 400 });
  }

  if (payload.action === "delete") {
    await executeDeletion(payload.userId);
    return NextResponse.json({ ok: true, action: "delete" });
  }

  const data = await buildExport(payload.userId);
  return new NextResponse(JSON.stringify(data, null, 2), {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": `attachment; filename="inner-data-export.json"`,
    },
  });
}
