interface ProgressBarProps {
  current: number;
  approxTotal: number;
  label?: string;
}

export function ProgressBar({ current, approxTotal, label }: ProgressBarProps) {
  const pct = Math.min(100, Math.round((current / Math.max(current, approxTotal)) * 100));
  return (
    <div>
      <div
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={Math.max(current, approxTotal)}
        aria-label={label ?? "Progress"}
        className="h-1 w-full overflow-hidden rounded-full bg-[var(--inner-line)]"
      >
        <div
          className="h-full rounded-full bg-[var(--inner-accent)] transition-[width] duration-300 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && (
        <p aria-hidden="true" className="mt-2 text-xs font-medium tracking-wide text-[var(--inner-muted)]">
          {label}
        </p>
      )}
    </div>
  );
}
