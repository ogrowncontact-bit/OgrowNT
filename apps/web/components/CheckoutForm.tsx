"use client";

import { useState } from "react";
import { Screen, Button, Checkbox } from "@inner/ui";

interface CheckoutFormProps {
  slug: string;
  assessmentSessionId: string;
  priceLabel: string;
}

const CONSENT_VERSION = "v1";

export function CheckoutForm({ slug, assessmentSessionId, priceLabel }: CheckoutFormProps) {
  const [email, setEmail] = useState("");
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function handleSubmit() {
    if (!emailValid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessmentSessionId, email, marketingConsent, consentVersion: CONSENT_VERSION }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Couldn't start checkout — please try again.");
      const data = await res.json();
      window.location.href = data.checkoutUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <Screen
      align="top"
      footer={
        <>
          <Button onClick={handleSubmit} disabled={!emailValid || submitting}>
            {submitting ? "..." : `Continue to Payment — ${priceLabel}`}
          </Button>
          {error && (
            <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
              {error}
            </p>
          )}
        </>
      }
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Almost there</p>
      <h1 id="checkout-email-heading" className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">
        Where should we send your report?
      </h1>

      <div className="mt-8">
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          aria-labelledby="checkout-email-heading"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-4 text-[16px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)] focus:border-[var(--inner-accent)] focus:outline-none"
        />

        <div className="mt-5">
          <Checkbox checked={marketingConsent} onChange={setMarketingConsent}>
            I&apos;d like to receive new INNER experiences, recommendations and updates by email.
          </Checkbox>
        </div>

        <p className="mt-4 text-xs leading-relaxed text-[var(--inner-muted)]">
          We&apos;ll always send your report to this address regardless of the box above — that&apos;s required to
          deliver what you&apos;re paying for. The box only controls future emails, and you can unsubscribe any time.
        </p>
      </div>
    </Screen>
  );
}
