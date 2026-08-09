import type { Business, Customer } from "@prisma/client";
import type { SendContext } from "../whatsapp/client";

export interface FlowContext {
  business: Business;
  wa: SendContext;
  customer: Customer;
  conversationId: string;
}
