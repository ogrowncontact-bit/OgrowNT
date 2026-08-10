import { apiFetch } from "./api";
import type { BusinessHoursEntry, Service } from "./types";

export function listServices(businessId: string, token: string): Promise<Service[]> {
  return apiFetch(`/api/businesses/${businessId}/services`, token);
}

export function createService(
  businessId: string,
  token: string,
  data: { name: string; durationMinutes: number; price?: number }
): Promise<Service> {
  return apiFetch(`/api/businesses/${businessId}/services`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateService(
  businessId: string,
  token: string,
  id: string,
  data: { active?: boolean; name?: string; durationMinutes?: number; price?: number | null }
): Promise<Service> {
  return apiFetch(`/api/businesses/${businessId}/services/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function listBusinessHours(businessId: string, token: string): Promise<BusinessHoursEntry[]> {
  return apiFetch(`/api/businesses/${businessId}/business-hours`, token);
}

export function saveBusinessHours(
  businessId: string,
  token: string,
  entries: { weekday: number; openTime: string; closeTime: string }[]
): Promise<BusinessHoursEntry[]> {
  return apiFetch(`/api/businesses/${businessId}/business-hours`, token, {
    method: "PUT",
    body: JSON.stringify(entries),
  });
}
