const COLORS: Record<string, string> = {
  quarantine: "bg-signal-red/15 text-signal-red border-signal-red/40",
  retired: "bg-ink-500/15 text-ink-500 border-ink-500/40",
  production: "bg-signal-green/15 text-signal-green border-signal-green/40",
  small_capital: "bg-signal-green/15 text-signal-green border-signal-green/40",
  paper: "bg-ink-100/10 text-ink-100 border-ink-100/30",
};

export function LifecycleBadge({ stage }: { stage: string }) {
  const cls = COLORS[stage] ?? "bg-ink-500/15 text-ink-500 border-ink-500/40";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {stage.replace(/_/g, " ")}
    </span>
  );
}
