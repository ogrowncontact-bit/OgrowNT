"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RefundButton({ orderId, amountLabel }: { orderId: string; amountLabel: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (!window.confirm(`Refund ${amountLabel}? This charges the reversal through the payment provider immediately.`)) return;

    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/refund`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? "Refund failed");
      }
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={submitting}
        className="text-[12px] text-[var(--inner-accent)] underline underline-offset-2 disabled:opacity-40"
      >
        {submitting ? "Refunding..." : "Refund"}
      </button>
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
