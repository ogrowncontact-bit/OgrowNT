"use client";

import { useEffect } from "react";

/** Mirrors LandingViewTracker.tsx — /explore is its own entry point, so it gets its own bootstrap+track beacon. */
export function ExploreViewTracker() {
  useEffect(() => {
    fetch("/api/events/explore-view", { method: "POST" }).catch(() => {});
  }, []);

  return null;
}
