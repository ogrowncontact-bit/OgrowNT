interface ProgressBarProps {
  current: number;
  approxTotal: number;
  label?: string;
}

export function ProgressBar({ current, approxTotal, label }: ProgressBarProps) {
  const pct = Math.min(100, Math.round((current / Math.max(current, approxTotal)) * 100));
  return (
    <div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--inner-line)]">
        <div
          className="h-full rounded-full bg-[var(--inner-accent)] transition-[width] duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && <p className="mt-2 text-xs font-medium tracking-wide text-[var(--inner-muted)]">{label}</p>}
    </div>
  );
}
