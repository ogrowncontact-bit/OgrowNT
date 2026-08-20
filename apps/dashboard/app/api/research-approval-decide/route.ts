import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { decideResearchApproval } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { approvalId, decision, detail } = await request.json();
  if (typeof approvalId !== "number" || typeof decision !== "string") {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }

  const result = await decideResearchApproval(token, approvalId, decision, typeof detail === "string" ? detail : undefined);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
