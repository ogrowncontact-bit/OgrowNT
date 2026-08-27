"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function ResolveTicketButton({ ticketId }: { ticketId: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function resolve() {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/support/${ticketId}/resolve`, { method: "POST" });
      if (res.ok) router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <button
      onClick={resolve}
      disabled={submitting}
      className="rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[12px] font-medium text-[var(--inner-ink)] disabled:opacity-50"
    >
      {submitting ? "…" : "Mark resolved"}
    </button>
  );
}
