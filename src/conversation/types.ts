import type { Business, Customer } from "@prisma/client";
import type { ChannelAdapter } from "../channels/types";

export interface FlowContext {
  business: Business;
  customer: Customer;
  conversationId: string;
  // Canal por onde essa conversa acontece - a logica de conversa/IA nunca
  // fala diretamente com WhatsApp/Instagram, so com essa interface (ver
  // src/channels/). recipientId e o identificador do cliente NESSE canal
  // (numero de telefone no WhatsApp; sera outro formato no Instagram).
  channel: ChannelAdapter;
  recipientId: string;
  // Idioma efetivo (ISO 639-1) para esta mensagem - resolvido em
  // src/language/detect.ts (deteccao > preferencia do cliente > padrao da
  // empresa). Tanto o fluxo guiado quanto a IA usam este valor, para nunca
  // divergir sobre em que idioma responder.
  language: string;
}
