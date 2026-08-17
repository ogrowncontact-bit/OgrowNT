/**
 * packages/ai has no persistence layer of its own (see docs/ARCHITECTURE.md
 * module boundaries — AI stays decoupled from storage), so cost/latency
 * monitoring works via a callback the app registers once at startup rather
 * than a direct DB write from in here.
 */
export interface AiCallEvent {
  module: string;
  model: string;
  latencyMs: number;
  inputTokens: number | null;
  outputTokens: number | null;
  ok: boolean;
  errorReason: string | null;
}

type TelemetryHandler = (event: AiCallEvent) => void;

let handler: TelemetryHandler | null = null;

export function onAiCall(fn: TelemetryHandler): void {
  handler = fn;
}

/** Never let a telemetry failure affect the actual AI call it's reporting on. */
export function reportAiCall(event: AiCallEvent): void {
  try {
    handler?.(event);
  } catch {
    // swallow — see above
  }
}
