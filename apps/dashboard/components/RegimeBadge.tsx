const COLORS: Record<string, string> = {
  trending_bull: "bg-signal-green/15 text-signal-green border-signal-green/40",
  trending_bear: "bg-signal-red/15 text-signal-red border-signal-red/40",
  ranging: "bg-ink-300/15 text-ink-300 border-ink-300/40",
  high_volatility: "bg-signal-orange/15 text-signal-orange border-signal-orange/40",
  low_volatility: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  panic: "bg-signal-red/25 text-signal-red border-signal-red/50",
  euphoria: "bg-signal-green/25 text-signal-green border-signal-green/50",
  transition: "bg-ink-300/15 text-ink-300 border-ink-300/40",
  unknown: "bg-ink-500/15 text-ink-500 border-ink-500/40",
};

export function RegimeBadge({ regime }: { regime: string }) {
  const cls = COLORS[regime] ?? COLORS.unknown;
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {regime.replace(/_/g, " ")}
    </span>
  );
}
