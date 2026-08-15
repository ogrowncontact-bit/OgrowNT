const COLORS: Record<string, string> = {
  watch: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  possible: "bg-ink-100/10 text-ink-100 border-ink-100/30",
  high_quality: "bg-signal-green/15 text-signal-green border-signal-green/40",
  exceptional: "bg-signal-green/25 text-signal-green border-signal-green/60",
};

export function TierBadge({ tier }: { tier: string }) {
  const cls = COLORS[tier] ?? "bg-ink-500/15 text-ink-500 border-ink-500/40";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {tier.replace(/_/g, " ")}
    </span>
  );
}
