import { apiFetch } from "./api";
import type { Automation, AutomationTrigger } from "./types";

export function listAutomations(businessId: string, token: string): Promise<Automation[]> {
  return apiFetch(`/api/businesses/${businessId}/automations`, token);
}

export function createAutomation(
  businessId: string,
  token: string,
  data: { trigger: AutomationTrigger; offsetMinutes: number }
): Promise<Automation> {
  return apiFetch(`/api/businesses/${businessId}/automations`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAutomation(
  businessId: string,
  token: string,
  id: string,
  data: { active?: boolean; offsetMinutes?: number }
): Promise<Automation> {
  return apiFetch(`/api/businesses/${businessId}/automations/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteAutomation(businessId: string, token: string, id: string): Promise<void> {
  return apiFetch(`/api/businesses/${businessId}/automations/${id}`, token, { method: "DELETE" });
}
