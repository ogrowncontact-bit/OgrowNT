import type { ReactNode } from "react";

interface ScreenProps {
  children: ReactNode;
  footer?: ReactNode;
  eyebrow?: ReactNode;
  /** Vertically center content (title-page feel — landing/result screens) vs. anchor it near the top (fast-scanning Q&A flow). Defaults to centered. */
  align?: "center" | "top";
}

/**
 * The one full-viewport container every mobile screen in the assessment
 * flow is built from — one primary action, a sticky footer CTA, generous
 * breathing room. See docs/ARCHITECTURE.md §9.1.
 */
export function Screen({ children, footer, eyebrow, align = "center" }: ScreenProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--inner-paper)] text-[var(--inner-ink)]">
      <div className="flex flex-1 flex-col px-6 pt-8" style={{ paddingBottom: footer ? "1rem" : "2rem" }}>
        {eyebrow && <div className="mb-6">{eyebrow}</div>}
        <div className={["flex flex-1 flex-col", align === "center" ? "justify-center" : "justify-start"].join(" ")}>
          {children}
        </div>
      </div>
      {footer && (
        <div
          className="sticky bottom-0 border-t border-[var(--inner-line)] bg-[var(--inner-paper)]/95 px-6 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 backdrop-blur"
        >
          {footer}
        </div>
      )}
    </div>
  );
}
