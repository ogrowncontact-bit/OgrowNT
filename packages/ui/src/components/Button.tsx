import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost";
}

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  const base =
    "w-full min-h-[52px] rounded-[var(--inner-radius-md)] px-6 text-[16px] font-medium tracking-wide transition-opacity duration-150 disabled:opacity-40";
  const styles =
    variant === "primary"
      ? "bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)] active:opacity-90"
      : "bg-transparent text-[var(--inner-ink-soft)] underline underline-offset-4";
  return <button className={[base, styles, className].filter(Boolean).join(" ")} {...props} />;
}
