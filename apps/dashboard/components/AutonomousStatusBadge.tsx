const COLORS: Record<string, string> = {
  starting: "bg-ink-100/10 text-ink-100 border-ink-100/40",
  running: "bg-signal-green/15 text-signal-green border-signal-green/40",
  paused: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  no_trade: "bg-ink-500/10 text-ink-300 border-ink-500/40",
  caution: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  defensive: "bg-signal-orange/15 text-signal-orange border-signal-orange/40",
  emergency: "bg-signal-red/15 text-signal-red border-signal-red/40",
  kill_switch: "bg-signal-red/20 text-signal-red border-signal-red/50",
  error: "bg-signal-red/20 text-signal-red border-signal-red/50",
};

export function AutonomousStatusBadge({ status }: { status: string }) {
  const cls = COLORS[status] ?? COLORS.starting;
  return (
    <span className={`inline-block rounded border px-2 py-1 text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}
