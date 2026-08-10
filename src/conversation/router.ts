import type { Business, WhatsAppAccount } from "@prisma/client";
import { runAiAgent } from "../ai/agent";
import { createWhatsAppAdapter } from "../channels/whatsapp";
import { findOrCreateCustomer } from "../customers";
import { prisma } from "../db";
import { resolveLanguage } from "../language/detect";
import type { IncomingMessage } from "../whatsapp/webhook";
import { STEP } from "./constants";
import * as stateMachine from "./stateMachine";
import type { FlowContext } from "./types";

// Ponto de entrada de toda mensagem recebida: garante cliente/conversa,
// grava no historico, e decide entre o fluxo guiado (respostas de botao/lista)
// e o agente de IA (texto livre) - nunca os dois ao mesmo tempo.
export async function routeIncomingMessage(
  business: Business,
  whatsAppAccount: WhatsAppAccount,
  fromPhoneNumber: string,
  contactName: string | undefined,
  message: IncomingMessage
): Promise<void> {
  const customer = await findOrCreateCustomer(business.id, fromPhoneNumber, contactName);

  const conversation = await prisma.conversation.upsert({
    where: { businessId_customerId: { businessId: business.id, customerId: customer.id } },
    update: {},
    create: { businessId: business.id, customerId: customer.id, step: STEP.IDLE },
  });

  const inboundContent = message.kind === "text" ? message.text : `[${message.replyTitle}]`;
  await prisma.message.create({
    data: {
      conversationId: conversation.id,
      direction: "IN",
      content: inboundContent,
      whatsAppMessageId: message.waMessageId,
    },
  });

  if (conversation.needsHuman) {
    // Um atendente humano assumiu a conversa; o bot fica em silencio ate ser
    // reativado manualmente (ver README/API de administracao).
    return;
  }

  // Deteccao de idioma (src/language/detect.ts): so ha texto livre para
  // analisar em mensagens de texto - respostas de botao/lista usam a
  // preferencia ja salva do cliente (ou o padrao da empresa). Nunca fica
  // "preso" a um idioma anterior: cada mensagem de texto e reavaliada.
  let language = customer.preferredLanguage !== "auto" ? customer.preferredLanguage : business.defaultLanguage;
  if (message.kind === "text") {
    const resolved = await resolveLanguage({
      text: message.text,
      supportedLanguages: business.supportedLanguages,
      preferredLanguage: customer.preferredLanguage,
      defaultLanguage: business.defaultLanguage,
    });
    language = resolved.language;

    if (resolved.detected && resolved.detected !== customer.preferredLanguage) {
      await prisma.customer.update({
        where: { id: customer.id },
        data: { preferredLanguage: resolved.detected },
      });
    }
    if (resolved.detected && resolved.detected !== conversation.detectedLanguage) {
      await prisma.conversation.update({
        where: { id: conversation.id },
        data: { detectedLanguage: resolved.detected },
      });
    }
  }

  const flowCtx: FlowContext = {
    business,
    customer,
    conversationId: conversation.id,
    language,
    // Fase 6: so WhatsApp esta implementado (ver src/channels/). Quando o
    // Instagram existir, este ponto escolhe o adapter certo a partir do
    // canal de origem do webhook, sem tocar no resto do fluxo.
    channel: createWhatsAppAdapter(whatsAppAccount),
    recipientId: fromPhoneNumber,
  };

  if (conversation.step === STEP.IDLE) {
    await stateMachine.sendMainMenu(flowCtx);
    await prisma.conversation.update({
      where: { id: conversation.id },
      data: { step: STEP.MENU, lastMessageAt: new Date() },
    });
    return;
  }

  if (message.kind === "interactive") {
    await stateMachine.handleInteractiveReply(flowCtx, conversation, message);
    return;
  }

  await runAiAgent(flowCtx);
}
