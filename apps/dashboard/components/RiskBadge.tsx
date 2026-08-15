const COLORS: Record<string, string> = {
  normal: "bg-signal-green/15 text-signal-green border-signal-green/40",
  caution: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  defensive: "bg-signal-orange/15 text-signal-orange border-signal-orange/40",
  emergency: "bg-signal-red/15 text-signal-red border-signal-red/40",
  kill_switch: "bg-ink-100/10 text-ink-100 border-ink-100/40",
};

export function RiskBadge({ level }: { level: string }) {
  const cls = COLORS[level] ?? COLORS.normal;
  return (
    <span className={`inline-block rounded border px-2 py-1 text-xs font-medium uppercase tracking-wide ${cls}`}>
      {level.replace("_", " ")}
    </span>
  );
}
