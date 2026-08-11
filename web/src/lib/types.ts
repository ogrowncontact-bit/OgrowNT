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

export type BookingStatus = "PENDING" | "CONFIRMED" | "CANCELLED" | "COMPLETED" | "NO_SHOW";

export interface Metrics {
  period: { days: number; since: string };
  conversations: {
    total: number;
    aiResolved: number;
    aiResolvedRate: number | null;
    needingHumanNow: number;
  };
  bookings: {
    total: number;
    byStatus: Record<BookingStatus, number>;
    upcomingConfirmed: number;
  };
  topServices: { serviceId: string; name: string; bookings: number }[];
  toolCalls: { total: number; successRate: number | null };
  messages: { in: number; out: number };
}

export type AutomationTrigger = "BOOKING_REMINDER" | "BOOKING_FOLLOWUP";

export interface Automation {
  id: string;
  businessId: string;
  trigger: AutomationTrigger;
  active: boolean;
  offsetMinutes: number;
  createdAt: string;
  updatedAt: string;
}

export interface Plan {
  id: string;
  key: string;
  name: string;
  priceMonthly: string;
  setupFee: string;
  currency: string;
  limits: Record<string, unknown>;
  active: boolean;
  createdAt: string;
}

export type SubscriptionStatus = "TRIALING" | "ACTIVE" | "PAST_DUE" | "CANCELED";

export interface Subscription {
  id: string;
  businessId: string;
  planId: string;
  status: SubscriptionStatus;
  setupFeePaid: boolean;
  trialEndsAt: string;
  currentPeriodEnd: string | null;
  createdAt: string;
  updatedAt: string;
  plan: Plan;
}

export interface BusinessProfile {
  id: string;
  name: string;
  slug: string;
  industry: string;
  timezone: string;
  description: string | null;
  address: string | null;
  phone: string | null;
  metadata: Record<string, unknown>;
  defaultLanguage: string;
  supportedLanguages: string[];
  currency: string;
}

export interface Service {
  id: string;
  businessId: string;
  name: string;
  durationMinutes: number;
  price: string | null;
  active: boolean;
  requiresResourceType: string | null;
  createdAt: string;
}

export interface BusinessHoursEntry {
  id: string;
  businessId: string;
  weekday: number;
  openTime: string;
  closeTime: string;
}

export interface OnboardingStatus {
  template: {
    industry: string;
    label: string;
    description: string;
    defaultServices: { name: string; durationMinutes: number }[];
  };
  checklist: {
    profileComplete: boolean;
    hasServices: boolean;
    hasBusinessHours: boolean;
    hasWhatsAppConnected: boolean;
  };
}

export interface QuickStartResult {
  createdServices: number;
  createdHours: boolean;
  message: string;
}

export interface WebsiteImportSuggestion {
  name: string;
  price: number | null;
  durationMinutes: number | null;
}

export interface WebsiteImportResult {
  sourceUrl: string;
  suggestions: WebsiteImportSuggestion[];
}

export type WhatsAppConnection =
  | { connected: false }
  | {
      connected: true;
      phoneNumberId: string;
      wabaId: string;
      verifiedName: string | null;
      connectedAt: string;
    };
