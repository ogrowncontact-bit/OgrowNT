import { apiFetch } from "./api";
import type { OnboardingStatus, QuickStartResult } from "./types";

export function getOnboarding(businessId: string, token: string): Promise<OnboardingStatus> {
  return apiFetch(`/api/businesses/${businessId}/onboarding`, token);
}

export function runQuickStart(businessId: string, token: string): Promise<QuickStartResult> {
  return apiFetch(`/api/businesses/${businessId}/onboarding/quick-start`, token, { method: "POST" });
}
