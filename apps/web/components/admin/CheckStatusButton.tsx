"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/** Manual reconciliation for a pending order — see lib/admin/orderReconciliation.ts for when this is actually needed. */
export function CheckStatusButton({ orderId }: { orderId: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleClick() {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/check-status`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error ?? "Check failed");
      setResult(data.status);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
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
        {submitting ? "Checking..." : "Check payment status"}
      </button>
      {result && <p className="mt-1 text-[11px] text-[var(--inner-muted)]">Provider says: {result}</p>}
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
