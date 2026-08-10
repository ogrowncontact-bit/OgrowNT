import { apiFetch } from "./api";
import type { Metrics } from "./types";

export function getMetrics(businessId: string, token: string, days: number): Promise<Metrics> {
  return apiFetch(`/api/businesses/${businessId}/metrics?days=${days}`, token);
}
