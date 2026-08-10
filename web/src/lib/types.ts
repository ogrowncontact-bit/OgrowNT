export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export type Role = "OWNER" | "ADMIN" | "STAFF";

export interface Membership {
  role: Role;
  business: {
    id: string;
    name: string;
    slug: string;
    industry: string;
  };
}

export interface TeamMember {
  userId: string;
  name: string;
  email: string;
  role: Role;
}

export type MessageSender = "CUSTOMER" | "AGENT" | "HUMAN" | "SYSTEM";
export type MessageDirection = "IN" | "OUT";

export interface Message {
  id: string;
  conversationId: string;
  direction: MessageDirection;
  sender: MessageSender;
  content: string;
  createdAt: string;
}

export interface ConversationNote {
  id: string;
  conversationId: string;
  userId: string;
  content: string;
  createdAt: string;
  user: { id: string; name: string };
}

export interface Customer {
  id: string;
  phoneNumber: string;
  name: string | null;
  preferredLanguage: string;
}

export interface ConversationListItem {
  id: string;
  businessId: string;
  customerId: string;
  step: string;
  needsHuman: boolean;
  channel: "WHATSAPP" | "INSTAGRAM";
  assignedToUserId: string | null;
  detectedLanguage: string | null;
  lastMessageAt: string;
  customer: Customer;
}

export interface ConversationDetail extends ConversationListItem {
  customer: Customer;
  assignedTo: { id: string; name: string; email: string } | null;
  messages: Message[];
  notes: ConversationNote[];
}
