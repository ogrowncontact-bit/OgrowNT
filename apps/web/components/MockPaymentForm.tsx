"use client";

import { useState } from "react";
import { Button } from "@inner/ui";

interface MockPaymentFormProps {
  orderId: string;
  /** Where a cancelled/declined payment sends the user back to, same as Stripe's real cancel_url. */
  cancelUrl: string;
}

export function MockPaymentForm({ orderId, cancelUrl }: MockPaymentFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleComplete() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/checkout/mock/${orderId}/complete`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Couldn't complete the test payment.");
      const data = await res.json();
      window.location.href = data.reportUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <div>
      <Button onClick={handleComplete} disabled={submitting}>
        {submitting ? "Generating your report..." : "Simulate Successful Payment"}
      </Button>
      <Button variant="ghost" onClick={() => (window.location.href = cancelUrl)} disabled={submitting} className="mt-2">
        Simulate Failed / Cancelled Payment
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
