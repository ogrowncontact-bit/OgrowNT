"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Checkbox } from "@inner/ui";

export function PreferenceToggle({ initialSubscribed }: { initialSubscribed: boolean }) {
  const router = useRouter();
  const [subscribed, setSubscribed] = useState(initialSubscribed);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleChange(next: boolean) {
    setSubscribed(next);
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subscribed: next }),
      });
      if (!res.ok) throw new Error("Couldn't save that — please try again.");
      router.refresh();
    } catch (e) {
      setSubscribed(!next); // revert on failure
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <Checkbox checked={subscribed} onChange={(checked) => !submitting && handleChange(checked)}>
        I&apos;d like to receive new INNER experiences, recommendations and updates by email.
      </Checkbox>
      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
