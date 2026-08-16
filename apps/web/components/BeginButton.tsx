"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@inner/ui";

export function BeginButton({ slug }: { slug: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function begin() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/sessions/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug,
          utm: {
            utm_source: searchParams.get("utm_source") ?? undefined,
            utm_medium: searchParams.get("utm_medium") ?? undefined,
            utm_campaign: searchParams.get("utm_campaign") ?? undefined,
            utm_content: searchParams.get("utm_content") ?? undefined,
            utm_term: searchParams.get("utm_term") ?? undefined,
          },
        }),
      });
      if (!res.ok) throw new Error("Could not start the experience. Please try again.");
      const data = await res.json();
      router.push(`/${slug}/session/${data.assessmentSessionId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={begin} disabled={loading}>
        {loading ? "One moment..." : "Begin"}
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
