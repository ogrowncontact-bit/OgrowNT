import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { postCommandQuery } from "@/lib/api";

// "PROMPT 14" §91-93: this route is a plain pass-through to
// POST /api/command-center/query — ALL safety classification (query vs.
// unauthorized) happens server-side in apps/api (packages/system/
// command_router.py). This Route Handler has no authority of its own and
// adds none; it exists only because client JS can't read the httpOnly auth
// cookie to call the FastAPI backend directly (the same reason every other
// mutating action in this dashboard goes through a Route Handler).
export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { text } = await request.json();
  if (typeof text !== "string" || !text.trim()) {
    return NextResponse.json({ detail: "text is required" }, { status: 400 });
  }

  const result = await postCommandQuery(token, text);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 403 });
  return NextResponse.json(result.result);
}
