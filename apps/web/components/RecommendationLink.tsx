"use client";

import Link from "next/link";

/** Fires recommendation_clicked before/while navigating — a plain <Link> has no click hook to attach analytics to. */
export function RecommendationLink({
  href,
  fromAssessmentId,
  toSlug,
  className,
  children,
}: {
  href: string;
  fromAssessmentId: string;
  toSlug: string;
  className?: string;
  children: React.ReactNode;
}) {
  function handleClick() {
    fetch("/api/events/recommendation-click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fromAssessmentId, toSlug }),
      keepalive: true,
    }).catch(() => {});
  }

  return (
    <Link href={href} onClick={handleClick} className={className}>
      {children}
    </Link>
  );
}
