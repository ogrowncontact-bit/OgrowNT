import type { ReactNode } from "react";

interface OptionCardProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  children?: ReactNode;
}

/** Large, thumb-friendly tap target — never a small radio button. */
export function OptionCard({ label, selected, onClick }: OptionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
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
