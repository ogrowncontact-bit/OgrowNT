"use client";

import { useState } from "react";
import { Button } from "@inner/ui";

export function PrivacyConfirmAction({ token, action }: { token: string; action: "export" | "delete" }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/privacy/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? "Something went wrong.");
      }

      if (action === "export") {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "inner-data-export.json";
        link.click();
        URL.revokeObjectURL(url);
      }

      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <p className="mt-6 text-[15px] text-[var(--inner-ink-soft)]">
        {action === "export" ? "Your download should have started." : "Your data has been deleted."}
      </p>
    );
  }

  return (
    <div className="mt-6">
      <Button onClick={handleConfirm} disabled={submitting}>
        {submitting ? "..." : action === "export" ? "Download My Data" : "Permanently Delete My Data"}
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
