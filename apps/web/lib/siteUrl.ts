/** Same APP_BASE_URL convention used throughout apps/web/lib (commerce.ts, access.ts, etc). */
export function getSiteUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}
