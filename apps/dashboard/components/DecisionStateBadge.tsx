const COLORS: Record<string, string> = {
  strong_long_bias: "bg-signal-green/25 text-signal-green border-signal-green/60",
  long_bias: "bg-signal-green/15 text-signal-green border-signal-green/40",
  neutral: "bg-ink-100/10 text-ink-100 border-ink-100/30",
  short_bias: "bg-signal-red/15 text-signal-red border-signal-red/40",
  strong_short_bias: "bg-signal-red/25 text-signal-red border-signal-red/60",
  no_trade: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  blocked: "bg-signal-red/25 text-signal-red border-signal-red/60",
};

export function DecisionStateBadge({ state }: { state: string }) {
  const cls = COLORS[state] ?? "bg-ink-500/15 text-ink-500 border-ink-500/40";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {state.replace(/_/g, " ")}
    </span>
  );
}
