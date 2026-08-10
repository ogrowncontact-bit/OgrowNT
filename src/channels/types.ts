export type ChannelType = "WHATSAPP" | "INSTAGRAM";

export interface ChannelListRow {
  id: string;
  title: string;
  description?: string;
}

export interface ChannelListSection {
  title: string;
  rows: ChannelListRow[];
}

export interface ChannelButton {
  id: string;
  title: string;
}

// Abstrai o envio de mensagens de um canal (WhatsApp, Instagram, ...) para
// que a camada de conversa/IA nunca dependa de detalhes de uma API
// especifica - "a logica da IA permanece independente do canal" (ver
// src/conversation/outbox.ts, o unico lugar que fala com um ChannelAdapter).
// Uma instancia e sempre ligada as credenciais de UMA empresa (multi-tenant).
export interface ChannelAdapter {
  readonly type: ChannelType;
  sendText(to: string, text: string): Promise<void>;
  sendList(to: string, opts: { bodyText: string; buttonText: string; sections: ChannelListSection[] }): Promise<void>;
  sendButtons(to: string, bodyText: string, buttons: ChannelButton[]): Promise<void>;
  // Mensagem fora da janela de conversa ativa (ex: lembretes proativos).
  // Nem todo canal tem esse conceito da mesma forma que o WhatsApp - adapters
  // sem suporte devem lancar ChannelNotImplementedError.
  sendTemplate(to: string, templateName: string, languageCode: string, components?: unknown[]): Promise<void>;
}
