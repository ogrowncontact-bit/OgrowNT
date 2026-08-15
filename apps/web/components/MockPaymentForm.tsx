"use client";

import { useState } from "react";
import { Button } from "@inner/ui";

export function MockPaymentForm({ orderId }: { orderId: string }) {
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
      {error && <p className="mt-3 text-sm text-[var(--inner-accent)]">{error}</p>}
    </div>
  );
}
