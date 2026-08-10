import type { WhatsAppAccount } from "@prisma/client";
import { decryptSecret } from "../crypto";
import * as waClient from "../whatsapp/client";
import type { ChannelAdapter } from "./types";

// Implementacao real do ChannelAdapter para WhatsApp - reaproveita 100% do
// cliente da Graph API ja existente (src/whatsapp/client.ts), so adapta a
// "forma" para a interface generica de canal. Nenhuma logica nova de envio
// aqui, so composicao.
export function createWhatsAppAdapter(account: WhatsAppAccount): ChannelAdapter {
  const waCtx: waClient.SendContext = {
    phoneNumberId: account.phoneNumberId,
    accessToken: decryptSecret(account.encryptedAccessToken),
  };

  return {
    type: "WHATSAPP",
    async sendText(to, text) {
      await waClient.sendTextMessage(waCtx, to, text);
    },
    async sendList(to, opts) {
      await waClient.sendListMessage(waCtx, to, opts);
    },
    async sendButtons(to, bodyText, buttons) {
      await waClient.sendButtonsMessage(waCtx, to, bodyText, buttons);
    },
    async sendTemplate(to, templateName, languageCode, components) {
      await waClient.sendTemplateMessage(waCtx, to, templateName, languageCode, components);
    },
  };
}
