import type { Business, WhatsAppAccount } from "@prisma/client";
import { runAiAgent } from "../ai/agent";
import { decryptSecret } from "../crypto";
import { findOrCreateCustomer } from "../customers";
import { prisma } from "../db";
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

  const flowCtx: FlowContext = {
    business,
    customer,
    conversationId: conversation.id,
    wa: {
      phoneNumberId: whatsAppAccount.phoneNumberId,
      accessToken: decryptSecret(whatsAppAccount.encryptedAccessToken),
    },
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
