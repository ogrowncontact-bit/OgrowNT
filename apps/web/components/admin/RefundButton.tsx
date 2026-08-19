"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { formatPrice } from "@/lib/money";

/** remainingCents defaults the amount field to a full refund of whatever hasn't already been refunded — the admin can lower it for a partial refund. */
export function RefundButton({ orderId, remainingCents, currency }: { orderId: string; remainingCents: number; currency: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState((remainingCents / 100).toFixed(2));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    const amountCents = Math.round(Number(amount) * 100);
    if (!Number.isFinite(amountCents) || amountCents <= 0 || amountCents > remainingCents) {
      setError(`Enter an amount up to ${formatPrice(remainingCents, currency)}`);
      return;
    }
    if (!window.confirm(`Refund ${formatPrice(amountCents, currency)}? This charges the reversal through the payment provider immediately.`)) return;

    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/refund`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amountCents }),
      });
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

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="text-[12px] text-[var(--inner-accent)] underline underline-offset-2">
        Refund
      </button>
    );
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex items-center gap-1">
        <input
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-20 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-1.5 py-0.5 text-[12px] text-[var(--inner-ink)]"
        />
        <button
          onClick={handleConfirm}
          disabled={submitting}
          className="text-[12px] text-[var(--inner-accent)] underline underline-offset-2 disabled:opacity-40"
        >
          {submitting ? "..." : "Confirm"}
        </button>
        <button onClick={() => setOpen(false)} className="text-[12px] text-[var(--inner-muted)]">
          Cancel
        </button>
      </div>
      {error && (
        <p role="alert" className="text-[11px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
