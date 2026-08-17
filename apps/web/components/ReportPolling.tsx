"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const POLL_INTERVAL_MS = 2500;
const MAX_ATTEMPTS = 20; // ~50s — generation is normally a few seconds; this is a generous ceiling, not an expected wait

/**
 * Polls for the report this session's server component just told us isn't
 * ready yet. Real (non-mock) Stripe redirects the browser to this page as
 * soon as checkout succeeds, before the webhook that actually runs
 * completeOrder() is guaranteed to have landed — so "not ready yet" is a
 * real, expected state to design for, not just a Phase-3 formality.
 */
export function ReportPolling() {
  const router = useRouter();
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let attempts = 0;
    const id = setInterval(() => {
      attempts += 1;
      if (attempts > MAX_ATTEMPTS) {
        clearInterval(id);
        setGaveUp(true);
        return;
      }
      router.refresh();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [router]);

  if (gaveUp) {
    return (
      <p className="mt-6 text-[14px] leading-relaxed text-[var(--inner-muted)]">
        This is taking longer than expected. Your payment went through, so your report is on its way to your inbox —
        or{" "}
        <a href="." className="underline">
          try refreshing this page
        </a>
        . Still nothing after a few minutes? <a href="/support" className="underline">Get help</a>.
      </p>
    );
  }

  return <span className="sr-only" role="status" aria-live="polite">Checking for your report…</span>;
}
