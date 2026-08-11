import { apiFetch } from "./api";
import type { BusinessProfile } from "./types";

export function getBusinessProfile(businessId: string, token: string): Promise<BusinessProfile> {
  return apiFetch(`/api/businesses/${businessId}`, token);
}

export function updateBusinessProfile(
  businessId: string,
  token: string,
  data: Partial<{
    name: string;
    description: string | null;
    address: string | null;
    phone: string | null;
    currency: string;
    defaultLanguage: string;
    supportedLanguages: string[];
  }>
): Promise<BusinessProfile> {
  return apiFetch(`/api/businesses/${businessId}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
