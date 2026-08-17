import { prisma } from "@inner/db";
import { onAiCall, type AiCallEvent } from "@inner/ai";

let registered = false;

/** Called once from instrumentation.ts. Idempotent — Next.js can invoke register() more than once in dev. */
export function ensureAiTelemetryRegistered(): void {
  if (registered) return;
  registered = true;

  onAiCall((event: AiCallEvent) => {
    prisma.aiCallLog
      .create({
        data: {
          module: event.module,
          model: event.model,
          latencyMs: event.latencyMs,
          inputTokens: event.inputTokens,
          outputTokens: event.outputTokens,
          ok: event.ok,
          errorReason: event.errorReason,
        },
      })
      .catch((err) => {
        // Telemetry must never take down the request it's reporting on.
        console.error("[ai-telemetry] failed to record AI call log", err);
      });
  });
}
