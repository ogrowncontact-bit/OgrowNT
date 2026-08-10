import { apiFetch } from "./api";
import type { WhatsAppConnection } from "./types";

export function getWhatsAppConnection(businessId: string, token: string): Promise<WhatsAppConnection> {
  return apiFetch(`/api/businesses/${businessId}/whatsapp`, token);
}

export function connectWhatsApp(
  businessId: string,
  token: string,
  data: { phoneNumberId: string; wabaId: string; accessToken: string; verifiedName?: string }
): Promise<WhatsAppConnection> {
  return apiFetch(`/api/businesses/${businessId}/whatsapp`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
