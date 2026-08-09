import { Prisma, type Conversation } from "@prisma/client";
import { prisma } from "../db";
import * as booking from "../booking/engine";
import { BookingConflictError } from "../booking/errors";
import type { IncomingInteractiveMessage } from "../whatsapp/webhook";
import { REPLY, STEP } from "./constants";
import { formatPrice, formatSlotShort } from "./format";
import * as outbox from "./outbox";
import type { FlowContext } from "./types";

// Fluxo guiado por botoes/listas: caminho principal e deterministico para
// agendar, ver, cancelar e remarcar. Chama sempre as mesmas funcoes de
// src/booking/engine.ts que o agente de IA usa, para nunca haver divergencia
// de regras entre os dois caminhos.

async function setConversationState(
  conversationId: string,
  step: string,
  data: Record<string, unknown> = {}
): Promise<void> {
  await prisma.conversation.update({
    where: { id: conversationId },
    data: { step, data: data as Prisma.InputJsonValue, lastMessageAt: new Date() },
  });
}

export async function sendMainMenu(ctx: FlowContext): Promise<void> {
  await outbox.sendList(ctx, {
    bodyText: `Ola! Aqui e o assistente virtual da ${ctx.business.name}. Como posso ajudar?`,
    buttonText: "Ver opcoes",
    sections: [
      {
        title: "Menu",
        rows: [
          { id: REPLY.MENU_BOOK, title: "Agendar horario" },
          { id: REPLY.MENU_MY_BOOKINGS, title: "Meus agendamentos" },
          { id: REPLY.MENU_CANCEL, title: "Cancelar/remarcar" },
          { id: REPLY.MENU_HUMAN, title: "Falar com atendente" },
        ],
      },
    ],
  });
}

async function backToMenu(ctx: FlowContext, conversationId: string): Promise<void> {
  await sendMainMenu(ctx);
  await setConversationState(conversationId, STEP.MENU);
}

async function sendServiceList(ctx: FlowContext): Promise<boolean> {
  const services = await prisma.service.findMany({
    where: { businessId: ctx.business.id, active: true },
    take: 10,
    orderBy: { name: "asc" },
  });

  if (services.length === 0) {
    await outbox.sendText(
      ctx,
      "No momento nao temos servicos configurados. Vou avisar um atendente para te ajudar."
    );
    return false;
  }

  await outbox.sendList(ctx, {
    bodyText: "Qual servico voce quer agendar?",
    buttonText: "Escolher servico",
    sections: [
      {
        title: "Servicos",
        rows: services.map((s) => ({
          id: s.id,
          title: s.name.slice(0, 24),
          description: [formatPrice(s.price), `${s.durationMinutes} min`].filter(Boolean).join(" - "),
        })),
      },
    ],
  });
  return true;
}

async function sendSlotList(ctx: FlowContext, serviceId: string): Promise<boolean> {
  const slots = await booking.getAvailableSlots(ctx.business.id, serviceId);
  if (slots.length === 0) {
    await outbox.sendText(
      ctx,
      "Nao encontrei horarios livres nos proximos dias para esse servico. Quer tentar outro servico ou falar com um atendente?"
    );
    return false;
  }

  await outbox.sendList(ctx, {
    bodyText: "Escolha um horario:",
    buttonText: "Ver horarios",
    sections: [
      {
        title: "Horarios disponiveis",
        rows: slots.map((s) => ({
          id: s.start.toISOString(),
          title: formatSlotShort(s.start, ctx.business.timezone),
        })),
      },
    ],
  });
  return true;
}

export async function handleInteractiveReply(
  ctx: FlowContext,
  conversation: Conversation,
  message: IncomingInteractiveMessage
): Promise<void> {
  const { replyId } = message;
  const data = conversation.data as Record<string, string | undefined>;

  switch (conversation.step) {
    case STEP.MENU: {
      if (replyId === REPLY.MENU_BOOK) {
        const ok = await sendServiceList(ctx);
        if (ok) {
          await setConversationState(conversation.id, STEP.CHOOSING_SERVICE);
        } else {
          await backToMenu(ctx, conversation.id);
        }
        return;
      }

      if (replyId === REPLY.MENU_MY_BOOKINGS) {
        const bookings = await booking.listUpcomingBookingsForCustomer(ctx.business.id, ctx.customer.id);
        if (bookings.length === 0) {
          await outbox.sendText(ctx, "Voce nao tem agendamentos futuros.");
        } else {
          const lines = bookings.map(
            (b) => `- ${b.service.name} em ${formatSlotShort(b.startsAt, ctx.business.timezone)}`
          );
          await outbox.sendText(ctx, lines.join("\n"));
        }
        await backToMenu(ctx, conversation.id);
        return;
      }

      if (replyId === REPLY.MENU_CANCEL) {
        const bookings = await booking.listUpcomingBookingsForCustomer(ctx.business.id, ctx.customer.id);
        if (bookings.length === 0) {
          await outbox.sendText(ctx, "Voce nao tem agendamentos futuros para cancelar ou remarcar.");
          await backToMenu(ctx, conversation.id);
          return;
        }
        await outbox.sendList(ctx, {
          bodyText: "Qual agendamento voce quer alterar?",
          buttonText: "Escolher",
          sections: [
            {
              title: "Seus agendamentos",
              rows: bookings.map((b) => ({
                id: b.id,
                title: formatSlotShort(b.startsAt, ctx.business.timezone),
                description: b.service.name,
              })),
            },
          ],
        });
        await setConversationState(conversation.id, STEP.CHOOSING_BOOKING_ACTION);
        return;
      }

      if (replyId === REPLY.MENU_HUMAN) {
        await prisma.conversation.update({ where: { id: conversation.id }, data: { needsHuman: true } });
        await outbox.sendText(ctx, "Certo! Um atendente humano vai te responder por aqui em breve.");
        return;
      }

      await backToMenu(ctx, conversation.id);
      return;
    }

    case STEP.CHOOSING_SERVICE: {
      const service = await prisma.service.findFirst({
        where: { id: replyId, businessId: ctx.business.id, active: true },
      });
      if (!service) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      const ok = await sendSlotList(ctx, service.id);
      if (ok) {
        await setConversationState(conversation.id, STEP.CHOOSING_SLOT, { serviceId: service.id });
      } else {
        await backToMenu(ctx, conversation.id);
      }
      return;
    }

    case STEP.CHOOSING_SLOT: {
      if (!data.serviceId) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      const startsAt = new Date(replyId);
      const service = await prisma.service.findUnique({ where: { id: data.serviceId } });
      if (Number.isNaN(startsAt.getTime()) || !service) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      await outbox.sendButtons(
        ctx,
        `Confirmar *${service.name}* em ${formatSlotShort(startsAt, ctx.business.timezone)}?`,
        [
          { id: REPLY.CONFIRM_YES, title: "Confirmar" },
          { id: REPLY.CONFIRM_NO, title: "Cancelar" },
        ]
      );
      await setConversationState(conversation.id, STEP.CONFIRMING, {
        serviceId: service.id,
        startsAt: startsAt.toISOString(),
      });
      return;
    }

    case STEP.CONFIRMING: {
      if (replyId === REPLY.CONFIRM_NO || !data.serviceId || !data.startsAt) {
        await outbox.sendText(ctx, "Sem problemas, agendamento nao confirmado.");
        await backToMenu(ctx, conversation.id);
        return;
      }

      if (replyId === REPLY.CONFIRM_YES) {
        try {
          const created = await booking.createBooking({
            businessId: ctx.business.id,
            customerId: ctx.customer.id,
            serviceId: data.serviceId,
            startsAt: new Date(data.startsAt),
          });
          await outbox.sendText(
            ctx,
            `Agendamento confirmado para ${formatSlotShort(created.startsAt, ctx.business.timezone)}. Te esperamos!`
          );
          await backToMenu(ctx, conversation.id);
        } catch (err) {
          if (err instanceof BookingConflictError) {
            await outbox.sendText(ctx, "Ih, esse horario acabou de ser reservado por outra pessoa. Vamos escolher outro?");
            const ok = await sendSlotList(ctx, data.serviceId);
            if (ok) {
              await setConversationState(conversation.id, STEP.CHOOSING_SLOT, { serviceId: data.serviceId });
            } else {
              await backToMenu(ctx, conversation.id);
            }
            return;
          }
          throw err;
        }
      }
      return;
    }

    case STEP.CHOOSING_BOOKING_ACTION: {
      const target = await prisma.booking.findFirst({
        where: { id: replyId, businessId: ctx.business.id, customerId: ctx.customer.id },
        include: { service: true },
      });
      if (!target) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      await outbox.sendButtons(
        ctx,
        `O que deseja fazer com ${target.service.name} em ${formatSlotShort(target.startsAt, ctx.business.timezone)}?`,
        [
          { id: REPLY.ACTION_CANCEL, title: "Cancelar" },
          { id: REPLY.ACTION_RESCHEDULE, title: "Remarcar" },
          { id: REPLY.ACTION_KEEP, title: "Manter" },
        ]
      );
      await setConversationState(conversation.id, STEP.BOOKING_ACTION, {
        bookingId: target.id,
        serviceId: target.serviceId,
      });
      return;
    }

    case STEP.BOOKING_ACTION: {
      if (!data.bookingId) {
        await backToMenu(ctx, conversation.id);
        return;
      }

      if (replyId === REPLY.ACTION_CANCEL) {
        await booking.cancelBooking(ctx.business.id, data.bookingId);
        await outbox.sendText(ctx, "Agendamento cancelado.");
        await backToMenu(ctx, conversation.id);
        return;
      }

      if (replyId === REPLY.ACTION_RESCHEDULE && data.serviceId) {
        const ok = await sendSlotList(ctx, data.serviceId);
        if (ok) {
          await setConversationState(conversation.id, STEP.CHOOSING_RESCHEDULE_SLOT, {
            bookingId: data.bookingId,
          });
        } else {
          await backToMenu(ctx, conversation.id);
        }
        return;
      }

      await outbox.sendText(ctx, "Ok, mantive seu agendamento como estava.");
      await backToMenu(ctx, conversation.id);
      return;
    }

    case STEP.CHOOSING_RESCHEDULE_SLOT: {
      if (!data.bookingId) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      const newStart = new Date(replyId);
      if (Number.isNaN(newStart.getTime())) {
        await backToMenu(ctx, conversation.id);
        return;
      }
      try {
        const updated = await booking.rescheduleBooking(ctx.business.id, data.bookingId, newStart);
        await outbox.sendText(
          ctx,
          `Prontinho, remarcado para ${formatSlotShort(updated.startsAt, ctx.business.timezone)}.`
        );
      } catch (err) {
        if (err instanceof BookingConflictError) {
          await outbox.sendText(ctx, "Esse horario acabou de ser ocupado. Vamos tentar outro?");
        } else {
          throw err;
        }
      }
      await backToMenu(ctx, conversation.id);
      return;
    }

    default: {
      await backToMenu(ctx, conversation.id);
    }
  }
}
