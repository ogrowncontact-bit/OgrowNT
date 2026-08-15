import type { ReactNode } from "react";

interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
}

/** Large, thumb-friendly consent checkbox — never pre-checked by a caller that means it as opt-in marketing consent. */
export function Checkbox({ checked, onChange, children }: CheckboxProps) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-1">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-5 w-5 shrink-0 rounded border-[var(--inner-line)] text-[var(--inner-accent)] focus:ring-[var(--inner-accent)]"
      />
      <span className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{children}</span>
    </label>
  );
}
