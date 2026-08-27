/**
 * Coarse device-family classification from a raw User-Agent string — mobile,
 * tablet, desktop, or unknown. Deliberately not a fingerprinting library:
 * good enough for admin breakdowns (FASE 33 §QUESTION ANALYTICS), never
 * precise enough to identify a specific device or browser version. The raw
 * UA itself is never persisted (see AnonymousSession.uaHash) — only this
 * bucket is.
 */
export function classifyDeviceType(userAgent: string): "mobile" | "tablet" | "desktop" | "unknown" {
  const ua = userAgent.toLowerCase();
  if (!ua || ua === "unknown") return "unknown";
  if (/ipad|tablet(?!.*mobile)/.test(ua)) return "tablet";
  if (/mobi|iphone|ipod|android.*mobile|windows phone/.test(ua)) return "mobile";
  if (/android/.test(ua)) return "tablet";
  return "desktop";
}
