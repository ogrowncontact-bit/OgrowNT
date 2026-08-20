"use client";

import { useEffect, useRef } from "react";
import { trackEvent } from "@/lib/clientTrack";

const THRESHOLDS = [25, 50, 75, 100];

/** FASE 23 §ANALYTICS — fires scroll_depth once per threshold per page load. */
export function ScrollDepthTracker({ slug }: { slug?: string }) {
  const firedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    function handleScroll() {
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - doc.clientHeight;
      const pct = scrollable <= 0 ? 100 : Math.round((doc.scrollTop / scrollable) * 100);

      for (const threshold of THRESHOLDS) {
        if (pct >= threshold && !firedRef.current.has(threshold)) {
          firedRef.current.add(threshold);
          trackEvent("scroll_depth", { slug, depth: threshold });
        }
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, [slug]);

  return null;
}
