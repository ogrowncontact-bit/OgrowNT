import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { updateIncident } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { incident_id, status, description } = await request.json();
  if (!Number.isInteger(incident_id)) {
    return NextResponse.json({ detail: "Invalid incident_id" }, { status: 400 });
  }

  const result = await updateIncident(token, incident_id, { status, description });
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 400 });
  return NextResponse.json(result.result);
}
