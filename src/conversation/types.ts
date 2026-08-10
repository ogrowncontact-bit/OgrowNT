import type { Business, Customer } from "@prisma/client";
import type { SendContext } from "../whatsapp/client";

export interface FlowContext {
  business: Business;
  wa: SendContext;
  customer: Customer;
  conversationId: string;
  // Idioma efetivo (ISO 639-1) para esta mensagem - resolvido em
  // src/language/detect.ts (deteccao > preferencia do cliente > padrao da
  // empresa). Tanto o fluxo guiado quanto a IA usam este valor, para nunca
  // divergir sobre em que idioma responder.
  language: string;
}
