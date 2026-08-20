"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const DECISION_LABEL: Record<string, string> = {
  approved: "Approve",
  rejected: "Reject",
  request_more_tests: "More Tests",
};

export function ApprovalDecisionButtons({
  approvalId,
  entityType,
  action,
}: {
  approvalId: number;
  entityType: string;
  action: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);

  async function decide(decision: string) {
    if (!window.confirm(`${DECISION_LABEL[decision]} this ${entityType} (${action})?`)) return;
    setPending(decision);
    try {
      await fetch("/api/research-approval-decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approvalId, decision }),
      });
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex gap-1">
      <button
        onClick={() => decide("approved")}
        disabled={pending !== null}
        className="rounded border border-signal-green/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50"
      >
        {pending === "approved" ? "…" : "Approve"}
      </button>
      <button
        onClick={() => decide("rejected")}
        disabled={pending !== null}
        className="rounded border border-signal-red/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-red transition hover:bg-signal-red/10 disabled:opacity-50"
      >
        {pending === "rejected" ? "…" : "Reject"}
      </button>
      <button
        onClick={() => decide("request_more_tests")}
        disabled={pending !== null}
        className="rounded border border-signal-yellow/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-yellow transition hover:bg-signal-yellow/10 disabled:opacity-50"
      >
        {pending === "request_more_tests" ? "…" : "More Tests"}
      </button>
    </div>
  );
}
