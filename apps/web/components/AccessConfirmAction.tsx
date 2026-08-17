"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@inner/ui";

export function AccessConfirmAction({ token }: { token: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/access/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? "Something went wrong.");
      }
      router.push("/access/reports");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-6">
      <Button onClick={handleConfirm} disabled={submitting}>
        {submitting ? "..." : "Access My Reports"}
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
