"use client";

import { useState } from "react";
import { Button } from "@inner/ui";

// Checkout wiring lands in Phase 3 (Stripe). This keeps the paywall screen
// demoable now without pretending to take a real payment.
export function PaywallCTA({ label }: { label: string }) {
  const [clicked, setClicked] = useState(false);
  return (
    <div>
      <Button onClick={() => setClicked(true)}>{label}</Button>
      {clicked && (
        <p className="mt-3 text-center text-sm text-[var(--inner-muted)]">
          Checkout isn&apos;t wired up yet — payments arrive in Phase 3.
        </p>
      )}
    </div>
  );
}
