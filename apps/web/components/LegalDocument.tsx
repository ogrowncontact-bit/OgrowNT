import type { ReactNode } from "react";
import Link from "next/link";
import { Screen } from "@inner/ui";

interface LegalDocumentProps {
  title: string;
  lastUpdated: string;
  children: ReactNode;
}

/**
 * Shared chrome for /terms and /privacy-policy: both are placeholder legal
 * text (docs/ARCHITECTURE.md §14 — drafted to unblock development, not
 * reviewed by a lawyer) and need the same unmissable notice plus a link to
 * the other document, so it lives once here instead of duplicated per page.
 */
export function LegalDocument({ title, lastUpdated, children }: LegalDocumentProps) {
  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Legal</p>
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">{title}</h1>
      <p className="mt-2 text-[13px] text-[var(--inner-muted)]">Last updated: {lastUpdated}</p>

      <div className="mt-6 rounded-[var(--inner-radius-md)] border border-[var(--inner-accent)]/40 bg-[var(--inner-paper-dim)] p-4">
        <p className="text-[13px] font-semibold leading-relaxed text-[var(--inner-accent)]">
          Placeholder — not yet reviewed by a lawyer
        </p>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
          This document was drafted to describe how INNER actually works today, so the site isn&apos;t launching
          without one. It is not final and must not be relied on as binding legal terms until a qualified lawyer has
          reviewed it and the bracketed placeholders below have been filled in.
        </p>
      </div>

      <div className="mt-8 space-y-6 pb-16 text-[15px] leading-relaxed text-[var(--inner-ink-soft)] [&_h2]:mt-8 [&_h2]:font-display [&_h2]:text-[18px] [&_h2]:text-[var(--inner-ink)] [&_h2]:first:mt-0 [&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:mt-1.5">
        {children}
      </div>

      <p className="border-t border-[var(--inner-line)] pb-8 pt-6 text-[13px] text-[var(--inner-muted)]">
        See also: <Link href="/terms" className="underline">Terms of Service</Link> ·{" "}
        <Link href="/privacy-policy" className="underline">Privacy Policy</Link> ·{" "}
        <Link href="/cookies" className="underline">Cookie Policy</Link> ·{" "}
        <Link href="/refund" className="underline">Refund Policy</Link> ·{" "}
        <Link href="/privacy" className="underline">Access, export or delete your data</Link>
      </p>
    </Screen>
  );
}
