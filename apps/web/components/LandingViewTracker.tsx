"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

export function LandingViewTracker({ slug }: { slug: string }) {
  const searchParams = useSearchParams();

  useEffect(() => {
    fetch("/api/events/landing-view", {
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
      // best-effort; a failed beacon shouldn't block or alarm the visitor
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  return null;
}
