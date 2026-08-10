import type { MessageSender } from "@prisma/client";
import type { ChannelButton, ChannelListSection } from "../channels/types";
import { prisma } from "../db";
import type { FlowContext } from "./types";

// Envia (via ctx.channel - ChannelAdapter, nunca uma API de canal
// diretamente) e grava no historico (Message) ao mesmo tempo, para que a
// conversa completa fique auditavel no banco - usado tanto pelo fluxo guiado
// quanto pelo agente de IA quanto pelas respostas humanas do Inbox (Fase 7).
// Este e o UNICO lugar da camada de conversa que fala com um canal - por
// isso a logica de conversa/IA nunca precisa saber se esta rodando no
// WhatsApp, Instagram ou outro canal futuro.

async function logOutbound(conversationId: string, content: string, sender: MessageSender) {
  await prisma.message.create({ data: { conversationId, direction: "OUT", sender, content } });
}

// sender default AGENT: todo o fluxo guiado e o agente de IA passam por aqui
// sem precisar declarar quem esta falando. As rotas de resposta humana do
// Inbox (Fase 7) passam sender: "HUMAN" explicitamente.
export async function sendText(ctx: FlowContext, text: string, sender: MessageSender = "AGENT"): Promise<void> {
  await ctx.channel.sendText(ctx.recipientId, text);
  await logOutbound(ctx.conversationId, text, sender);
}

export async function sendList(
  ctx: FlowContext,
  opts: { bodyText: string; buttonText: string; sections: ChannelListSection[] },
  sender: MessageSender = "AGENT"
): Promise<void> {
  await ctx.channel.sendList(ctx.recipientId, opts);
  await logOutbound(ctx.conversationId, opts.bodyText, sender);
}

export async function sendButtons(
  ctx: FlowContext,
  bodyText: string,
  buttons: ChannelButton[],
  sender: MessageSender = "AGENT"
): Promise<void> {
  await ctx.channel.sendButtons(ctx.recipientId, bodyText, buttons);
  await logOutbound(ctx.conversationId, bodyText, sender);
}
