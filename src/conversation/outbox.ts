import type { ChannelButton, ChannelListSection } from "../channels/types";
import { prisma } from "../db";
import type { FlowContext } from "./types";

// Envia (via ctx.channel - ChannelAdapter, nunca uma API de canal
// diretamente) e grava no historico (Message) ao mesmo tempo, para que a
// conversa completa fique auditavel no banco - usado tanto pelo fluxo guiado
// quanto pelo agente de IA. Este e o UNICO lugar da camada de conversa que
// fala com um canal - por isso a logica de conversa/IA nunca precisa saber
// se esta rodando no WhatsApp, Instagram ou outro canal futuro.

async function logOutbound(conversationId: string, content: string) {
  await prisma.message.create({ data: { conversationId, direction: "OUT", content } });
}

export async function sendText(ctx: FlowContext, text: string): Promise<void> {
  await ctx.channel.sendText(ctx.recipientId, text);
  await logOutbound(ctx.conversationId, text);
}

export async function sendList(
  ctx: FlowContext,
  opts: { bodyText: string; buttonText: string; sections: ChannelListSection[] }
): Promise<void> {
  await ctx.channel.sendList(ctx.recipientId, opts);
  await logOutbound(ctx.conversationId, opts.bodyText);
}

export async function sendButtons(ctx: FlowContext, bodyText: string, buttons: ChannelButton[]): Promise<void> {
  await ctx.channel.sendButtons(ctx.recipientId, bodyText, buttons);
  await logOutbound(ctx.conversationId, bodyText);
}
