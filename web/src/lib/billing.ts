import { apiFetch } from "./api";
import type { Plan, Subscription } from "./types";

export function listPlans(): Promise<Plan[]> {
  return apiFetch("/api/plans", null);
}

export function getSubscription(businessId: string, token: string): Promise<Subscription> {
  return apiFetch(`/api/businesses/${businessId}/subscription`, token);
}

export function changePlan(businessId: string, token: string, planKey: string): Promise<Subscription> {
  return apiFetch(`/api/businesses/${businessId}/subscription/plan`, token, {
    method: "POST",
    body: JSON.stringify({ planKey }),
  });
}

export function startCheckout(businessId: string, token: string): Promise<void> {
  return apiFetch(`/api/businesses/${businessId}/subscription/checkout`, token, { method: "POST" });
}
