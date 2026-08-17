import type { ReactNode } from "react";

interface LoadingStateProps {
  eyebrow: string;
  title: string;
  body?: ReactNode;
}

/** Full-screen async-wait state — report generation, PDF rendering, anything that takes a beat. Static, not animated: see docs/ARCHITECTURE.md §9 on keeping the interface calm. */
export function LoadingState({ eyebrow, title, body }: LoadingStateProps) {
  return (
    <div role="status" aria-live="polite">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">{eyebrow}</p>
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">{title}</h1>
      {body && <div className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{body}</div>}
    </div>
  );
}
