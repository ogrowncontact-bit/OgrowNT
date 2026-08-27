import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const COOKIE_NAME = "ogrownt_token";

// A native browser WebSocket can't set an Authorization header, so the
// dashboard's client-side WS hook (lib/useEventStream.ts) calls this route
// once to get the SAME admin JWT the REST API already uses, passed as
// ?token= on the WS handshake instead. This route is the only place client
// JS can ever see the token's value — it reads the httpOnly ogrownt_token
// cookie server-side (client JS can never read an httpOnly cookie itself)
// and hands it back over the same-origin connection the rest of this
// dashboard already trusts. No new credential is minted; this is not a
// second auth system.
export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  return NextResponse.json({ token });
}
