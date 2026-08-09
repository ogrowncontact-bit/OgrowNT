import { createHmac, timingSafeEqual } from "node:crypto";
import { config } from "../config";

// Valida o header X-Hub-Signature-256 que a Meta envia em todo webhook,
// calculado como HMAC-SHA256 do corpo bruto da requisicao usando o App Secret.
export function verifySignature(rawBody: Buffer, signatureHeader: string | undefined): boolean {
  if (!signatureHeader || !config.whatsapp.appSecret) return false;
  const expected = `sha256=${createHmac("sha256", config.whatsapp.appSecret).update(rawBody).digest("hex")}`;
  const sigBuf = Buffer.from(signatureHeader);
  const expBuf = Buffer.from(expected);
  if (sigBuf.length !== expBuf.length) return false;
  return timingSafeEqual(sigBuf, expBuf);
}

export interface IncomingTextMessage {
  kind: "text";
  from: string;
  waMessageId: string;
  text: string;
}

export interface IncomingInteractiveMessage {
  kind: "interactive";
  from: string;
  waMessageId: string;
  replyId: string; // id do botao ou da linha da lista escolhida
  replyTitle: string;
}

export type IncomingMessage = IncomingTextMessage | IncomingInteractiveMessage;

export interface ParsedWebhookEntry {
  phoneNumberId: string;
  messages: IncomingMessage[];
  contactNames: Record<string, string>; // waId -> nome de perfil
}

// Formato do payload: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
// Tipado frouxamente de proposito (payload externo, estrutura ampla da Meta).
export function parseIncomingWebhook(payload: any): ParsedWebhookEntry[] {
  const results: ParsedWebhookEntry[] = [];

  for (const entry of payload?.entry ?? []) {
    for (const change of entry?.changes ?? []) {
      const value = change?.value;
      if (!value?.messages) continue;

      const phoneNumberId = value.metadata?.phone_number_id;
      const contactNames: Record<string, string> = {};
      for (const c of value.contacts ?? []) {
        if (c?.wa_id) contactNames[c.wa_id] = c.profile?.name;
      }

      const messages: IncomingMessage[] = [];
      for (const m of value.messages) {
        if (m.type === "text" && m.text?.body) {
          messages.push({ kind: "text", from: m.from, waMessageId: m.id, text: m.text.body });
        } else if (m.type === "interactive") {
          const interactive = m.interactive;
          if (interactive?.type === "list_reply") {
            messages.push({
              kind: "interactive",
              from: m.from,
              waMessageId: m.id,
              replyId: interactive.list_reply.id,
              replyTitle: interactive.list_reply.title,
            });
          } else if (interactive?.type === "button_reply") {
            messages.push({
              kind: "interactive",
              from: m.from,
              waMessageId: m.id,
              replyId: interactive.button_reply.id,
              replyTitle: interactive.button_reply.title,
            });
          }
        }
      }

      if (messages.length > 0 && phoneNumberId) {
        results.push({ phoneNumberId, messages, contactNames });
      }
    }
  }

  return results;
}
