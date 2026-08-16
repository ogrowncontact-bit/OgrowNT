import type { ReactNode } from "react";

interface OptionCardProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  children?: ReactNode;
  /** "radio" for a single-select group (one answer), "checkbox" for multi-select (several answers). Defaults to "checkbox" — a plain toggle. */
  variant?: "radio" | "checkbox";
}

/** Large, thumb-friendly tap target — never a small radio button, but exposes real radio/checkbox semantics to assistive tech via role + aria-checked. */
export function OptionCard({ label, selected, onClick, variant = "checkbox" }: OptionCardProps) {
  return (
    <button
      type="button"
      role={variant}
      onClick={onClick}
      aria-checked={selected ?? false}
      className={[
        "w-full rounded-[var(--inner-radius-md)] border px-5 py-4 text-left text-[17px] leading-snug transition-colors duration-150",
        "min-h-[56px] active:scale-[0.99]",
        selected
          ? "border-[var(--inner-accent)] bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)]"
          : "border-[var(--inner-line)] bg-[var(--inner-card)] text-[var(--inner-ink)] hover:border-[var(--inner-accent-soft)]",
      ].join(" ")}
    >
      {label}
    </button>
  );
}
