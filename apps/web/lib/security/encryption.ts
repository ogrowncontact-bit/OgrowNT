import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from "node:crypto";

// Open-text answers are the most sensitive data INNER collects (§12) — encrypted
// at rest with AES-256-GCM. Key is derived from SESSION_SECRET for local dev;
// production should set a dedicated 32-byte ENCRYPTION_KEY instead (see .env.example).
const keyMaterial = process.env.ENCRYPTION_KEY ?? process.env.SESSION_SECRET ?? "dev-only-change-me";
const key = scryptSync(keyMaterial, "inner-open-response-salt", 32);

export function encryptText(plaintext: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, tag, encrypted]).toString("base64");
}

export function decryptText(payload: string): string {
  const buf = Buffer.from(payload, "base64");
  const iv = buf.subarray(0, 12);
  const tag = buf.subarray(12, 28);
  const encrypted = buf.subarray(28);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(encrypted), decipher.final()]).toString("utf8");
}
