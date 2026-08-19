import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getLabJob } from "@/lib/api";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { id } = await params;
  const jobId = Number(id);
  if (!Number.isInteger(jobId)) return NextResponse.json({ detail: "Invalid job id" }, { status: 400 });

  const job = await getLabJob(token, jobId);
  if (!job) return NextResponse.json({ detail: "Job not found" }, { status: 404 });
  return NextResponse.json(job);
}
