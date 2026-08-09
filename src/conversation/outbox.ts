import { prisma } from "../db";
import * as waClient from "../whatsapp/client";
import type { FlowContext } from "./types";

// Envia e grava no historico (Message) ao mesmo tempo, para que a conversa
// completa fique auditavel no banco - usado tanto pelo fluxo guiado quanto
// pelo agente de IA.

async function logOutbound(conversationId: string, content: string) {
  await prisma.message.create({ data: { conversationId, direction: "OUT", content } });
}

export async function sendText(ctx: FlowContext, text: string): Promise<void> {
  await waClient.sendTextMessage(ctx.wa, ctx.customer.phoneNumber, text);
  await logOutbound(ctx.conversationId, text);
}

export async function sendList(
  ctx: FlowContext,
  opts: { bodyText: string; buttonText: string; sections: waClient.ListSection[] }
): Promise<void> {
  await waClient.sendListMessage(ctx.wa, ctx.customer.phoneNumber, opts);
  await logOutbound(ctx.conversationId, opts.bodyText);
}

export async function sendButtons(
  ctx: FlowContext,
  bodyText: string,
  buttons: waClient.ReplyButton[]
): Promise<void> {
  await waClient.sendButtonsMessage(ctx.wa, ctx.customer.phoneNumber, bodyText, buttons);
  await logOutbound(ctx.conversationId, bodyText);
}
