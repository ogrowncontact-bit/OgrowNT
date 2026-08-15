import { createHmac, timingSafeEqual } from "node:crypto";

const secret = process.env.SESSION_SECRET ?? "dev-only-change-me";

function hmac(value: string): string {
  return createHmac("sha256", secret).update(value).digest("hex");
}

/** Signs an anonymous session id so the cookie can't be trivially forged into a different session id. */
export function signSessionToken(anonymousSessionId: string): string {
  return `${anonymousSessionId}.${hmac(anonymousSessionId)}`;
}

export function verifySessionToken(token: string | undefined | null): string | null {
  if (!token) return null;
  const [id, sig] = token.split(".");
  if (!id || !sig) return null;
  const expected = hmac(id);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  return id;
}

export function hashIdentifier(value: string): string {
  return hmac(value);
}
