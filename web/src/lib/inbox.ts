import { apiFetch } from "./api";
import type { ConversationDetail, ConversationListItem, ConversationNote, TeamMember } from "./types";

export function listConversations(
  businessId: string,
  token: string,
  needsHuman?: boolean
): Promise<ConversationListItem[]> {
  const query = needsHuman === undefined ? "" : `?needsHuman=${needsHuman}`;
  return apiFetch(`/api/businesses/${businessId}/conversations${query}`, token);
}

export function getConversation(businessId: string, token: string, conversationId: string): Promise<ConversationDetail> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}`, token);
}

export function sendHumanReply(businessId: string, token: string, conversationId: string, text: string): Promise<void> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}/messages`, token, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function assignConversation(
  businessId: string,
  token: string,
  conversationId: string,
  userId: string | null
): Promise<ConversationDetail> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}/assign`, token, {
    method: "POST",
    body: JSON.stringify({ userId }),
  });
}

export function handoffConversation(businessId: string, token: string, conversationId: string): Promise<void> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}/handoff`, token, { method: "POST" });
}

export function resolveConversation(businessId: string, token: string, conversationId: string): Promise<void> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}/resolve`, token, { method: "POST" });
}

export function addNote(businessId: string, token: string, conversationId: string, content: string): Promise<ConversationNote> {
  return apiFetch(`/api/businesses/${businessId}/conversations/${conversationId}/notes`, token, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function listMembers(businessId: string, token: string): Promise<TeamMember[]> {
  return apiFetch(`/api/businesses/${businessId}/members`, token);
}
