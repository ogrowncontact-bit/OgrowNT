"use client";

/**
 * Shared client-side beacon for the generic /api/events allowlisted events
 * (hero_cta_clicked, scroll_depth, faq_opened, premium_preview_viewed, ...).
 * Best-effort, same as every other client tracker in this app — a failed
 * beacon must never block or alarm the visitor. Never pass raw answer text.
 */
export function trackEvent(eventName: string, properties?: Record<string, unknown>): void {
  fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ eventName, properties }),
  }).catch(() => {});
}
