"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@inner/ui";
import type { AssessmentCtaState } from "@/lib/assessmentCtaState";
import { CTA_LABELS } from "@/lib/assessmentCtaState";
import { trackEvent } from "@/lib/clientTrack";

/**
 * FASE 23 §CTA LOGIC — one component driving both the hero CTA and the
 * Final CTA section, so the two never drift out of sync. `ctaState` is
 * computed server-side (lib/assessmentCtaState.ts) from the visitor's real
 * session/entitlement history for this assessment; this component only
 * decides how to act on it — start a brand-new session (same POST
 * /api/sessions/start flow BeginButton used), or simply navigate to an
 * existing one.
 */
export function AssessmentCTA({ slug, ctaState, label }: { slug: string; ctaState: AssessmentCtaState; label?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayLabel = label?.trim() || CTA_LABELS[ctaState.kind];

  async function begin() {
    setLoading(true);
    setError(null);
    trackEvent("hero_cta_clicked", { slug, kind: ctaState.kind });
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
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.message || "Could not start the experience. Please try again.");
      }
      const data = await res.json();
      router.push(`/${slug}/session/${data.assessmentSessionId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setLoading(false);
    }
  }

  if (ctaState.kind !== "start") {
    return (
      <Link
        href={ctaState.href}
        onClick={() => trackEvent("hero_cta_clicked", { slug, kind: ctaState.kind })}
        className="block rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-4 text-center text-[16px] font-medium text-[var(--inner-accent-contrast)]"
      >
        {displayLabel}
      </Link>
    );
  }

  return (
    <div>
      <Button onClick={begin} disabled={loading}>
        {loading ? "One moment..." : displayLabel}
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}
