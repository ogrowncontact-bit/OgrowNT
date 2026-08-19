import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Resend signs webhook deliveries using Svix's standard scheme (svix-id /
 * svix-timestamp / svix-signature headers, HMAC-SHA256 over
 * "id.timestamp.body" using the base64 portion of a whsec_... secret).
 * Hand-rolled rather than pulling in the `svix` package — same
 * already-established pattern as lib/security/signedToken.ts.
 */
const TOLERANCE_MS = 5 * 60 * 1000;

export function verifySvixSignature(params: {
  secret: string;
  svixId: string | null;
  svixTimestamp: string | null;
  svixSignature: string | null;
  rawBody: string;
}): boolean {
  const { secret, svixId, svixTimestamp, svixSignature, rawBody } = params;
  if (!svixId || !svixTimestamp || !svixSignature) return false;

  const timestampMs = Number(svixTimestamp) * 1000;
  if (!Number.isFinite(timestampMs) || Math.abs(Date.now() - timestampMs) > TOLERANCE_MS) return false;

  const secretBytes = Buffer.from(secret.replace(/^whsec_/, ""), "base64");
  const signedContent = `${svixId}.${svixTimestamp}.${rawBody}`;
  const expectedBuf = createHmac("sha256", secretBytes).update(signedContent).digest();

  return svixSignature.split(" ").some((part) => {
    const sig = part.startsWith("v1,") ? part.slice(3) : part;
    let sigBuf: Buffer;
    try {
      sigBuf = Buffer.from(sig, "base64");
    } catch {
      return false;
    }
    return sigBuf.length === expectedBuf.length && timingSafeEqual(sigBuf, expectedBuf);
  });
}
