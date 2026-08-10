import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, currentUser, requireMembership } from "../auth/middleware";
import { createInstagramAdapter } from "../channels/instagram";
import { createWhatsAppAdapter } from "../channels/whatsapp";
import { ChannelNotImplementedError } from "../channels/errors";
import * as outbox from "../conversation/outbox";
import type { FlowContext } from "../conversation/types";
import { prisma } from "../db";

// Rotas do Inbox (Fase 7): atendimento humano por cima da mesma conversa que
// o bot usa. Montado em /api/businesses/:businessId (ver server.ts).
export const inboxRouter = Router({ mergeParams: true });

inboxRouter.use(requireMembership);

async function loadConversationOr404(businessId: string, conversationId: string) {
  return prisma.conversation.findFirst({ where: { id: conversationId, businessId } });
}

// Constroi o ChannelAdapter certo para o canal da conversa - mesma logica de
// escolha usada em src/conversation/router.ts, so que aqui a origem e a
// resposta manual de um atendente, nao um webhook.
async function channelForConversation(businessId: string, channel: "WHATSAPP" | "INSTAGRAM") {
  if (channel === "INSTAGRAM") {
    return createInstagramAdapter();
  }
  const account = await prisma.whatsAppAccount.findUnique({ where: { businessId } });
  if (!account) {
    throw new ChannelNotImplementedError("WhatsApp", "Envio de mensagens (nenhuma conta conectada)");
  }
  return createWhatsAppAdapter(account);
}

inboxRouter.get(
  "/conversations/:id",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const conversation = await prisma.conversation.findFirst({
      where: { id: req.params.id, businessId: business.id },
      include: {
        customer: true,
        assignedTo: { select: { id: true, name: true, email: true } },
        messages: { orderBy: { createdAt: "asc" } },
        notes: { orderBy: { createdAt: "asc" }, include: { user: { select: { id: true, name: true } } } },
      },
    });
    if (!conversation) {
      res.sendStatus(404);
      return;
    }
    res.json(conversation);
  })
);

// Resposta manual de um atendente - passa pelo MESMO outbox que o bot usa
// (garante historico auditavel e reaproveita o ChannelAdapter), so que
// marcada com sender:"HUMAN". Nao altera o step da maquina de estados nem
// needsHuman - use /handoff e /resolve para isso.
inboxRouter.post(
  "/conversations/:id/messages",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { text } = req.body ?? {};
    if (!text || typeof text !== "string" || !text.trim()) {
      res.status(400).json({ error: "text e obrigatorio." });
      return;
    }

    const conversation = await prisma.conversation.findFirst({
      where: { id: req.params.id, businessId: business.id },
      include: { customer: true },
    });
    if (!conversation) {
      res.sendStatus(404);
      return;
    }

    try {
      const channel = await channelForConversation(business.id, conversation.channel);
      const ctx: FlowContext = {
        business,
        customer: conversation.customer,
        conversationId: conversation.id,
        channel,
        recipientId: conversation.customer.phoneNumber,
        language:
          conversation.customer.preferredLanguage !== "auto" ? conversation.customer.preferredLanguage : business.defaultLanguage,
      };

      await outbox.sendText(ctx, text.trim(), "HUMAN");
      await prisma.conversation.update({ where: { id: conversation.id }, data: { lastMessageAt: new Date() } });
      res.status(201).json({ ok: true });
    } catch (err) {
      if (err instanceof ChannelNotImplementedError) {
        res.status(501).json({ error: err.message });
        return;
      }
      throw err;
    }
  })
);

// Atribui (ou remove a atribuicao de) a conversa a um membro da equipe.
// userId: null desatribui. So aceita usuarios com Membership nesta empresa.
inboxRouter.post(
  "/conversations/:id/assign",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { userId } = req.body ?? {};

    const conversation = await loadConversationOr404(business.id, req.params.id);
    if (!conversation) {
      res.sendStatus(404);
      return;
    }

    if (userId !== null && userId !== undefined) {
      const membership = await prisma.membership.findUnique({
        where: { userId_businessId: { userId: String(userId), businessId: business.id } },
      });
      if (!membership) {
        res.status(400).json({ error: "userId nao e um membro desta empresa." });
        return;
      }
    }

    const updated = await prisma.conversation.update({
      where: { id: conversation.id },
      data: { assignedToUserId: userId ?? null },
      include: { assignedTo: { select: { id: true, name: true, email: true } } },
    });
    res.json(updated);
  })
);

// Marca a conversa como precisando de atendimento humano (pausa o bot) - o
// complemento de POST /conversations/:id/resolve (admin.routes.ts), que
// devolve a conversa ao bot.
inboxRouter.post(
  "/conversations/:id/handoff",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const conversation = await loadConversationOr404(business.id, req.params.id);
    if (!conversation) {
      res.sendStatus(404);
      return;
    }
    const updated = await prisma.conversation.update({
      where: { id: conversation.id },
      data: { needsHuman: true },
    });
    res.json(updated);
  })
);

// Nota interna da equipe - nunca enviada ao cliente (ver ConversationNote no
// schema).
inboxRouter.post(
  "/conversations/:id/notes",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const user = currentUser(res);
    const { content } = req.body ?? {};
    if (!content || typeof content !== "string" || !content.trim()) {
      res.status(400).json({ error: "content e obrigatorio." });
      return;
    }

    const conversation = await loadConversationOr404(business.id, req.params.id);
    if (!conversation) {
      res.sendStatus(404);
      return;
    }

    const note = await prisma.conversationNote.create({
      data: { conversationId: conversation.id, userId: user.id, content: content.trim() },
      include: { user: { select: { id: true, name: true } } },
    });
    res.status(201).json(note);
  })
);
