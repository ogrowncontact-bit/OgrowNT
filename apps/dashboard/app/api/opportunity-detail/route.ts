import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getOpportunityDetail } from "@/lib/api";

export async function GET(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const signalId = Number(new URL(request.url).searchParams.get("signal_id"));
  if (!Number.isInteger(signalId)) {
    return NextResponse.json({ detail: "Invalid signal_id" }, { status: 400 });
  }

  const detail = await getOpportunityDetail(token, signalId);
  if (!detail) return NextResponse.json({ detail: "Opportunity not found" }, { status: 404 });
  return NextResponse.json(detail);
}
