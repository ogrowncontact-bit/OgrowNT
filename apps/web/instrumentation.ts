// Next.js's supported one-time server-startup hook — the correct place to
// wire up cross-cutting, non-request-scoped setup like this rather than
// somewhere that would re-run per request or per route.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { ensureAiTelemetryRegistered } = await import("./lib/aiTelemetry");
    ensureAiTelemetryRegistered();
  }
}
