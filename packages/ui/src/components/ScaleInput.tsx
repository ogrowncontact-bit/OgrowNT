interface ScaleInputProps {
  max: number;
  value?: number;
  onChange: (value: number) => void;
  lowLabel: string;
  highLabel: string;
}

export function ScaleInput({ max, value, onChange, lowLabel, highLabel }: ScaleInputProps) {
  const steps = Array.from({ length: max }, (_, i) => i + 1);
  return (
    <div>
      <div className="flex justify-between gap-2">
        {steps.map((step) => (
          <button
            key={step}
            type="button"
            onClick={() => onChange(step)}
            aria-pressed={value === step}
            className={[
              "flex h-14 flex-1 items-center justify-center rounded-[var(--inner-radius-sm)] border text-[17px] font-medium transition-colors",
              value === step
                ? "border-[var(--inner-accent)] bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)]"
                : "border-[var(--inner-line)] bg-[var(--inner-card)] text-[var(--inner-ink)]",
            ].join(" ")}
          >
            {step}
          </button>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-[var(--inner-muted)]">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}
