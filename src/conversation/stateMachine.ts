import { Prisma, type Conversation } from "@prisma/client";
import { buildGreeting, getAgent } from "../ai/identity";
import { prisma } from "../db";
import * as booking from "../booking/engine";
import { BookingConflictError } from "../booking/errors";
import { getUiStrings } from "../language/strings";
import type { IncomingInteractiveMessage } from "../whatsapp/webhook";
import { REPLY, STEP } from "./constants";
import { formatPrice, formatSlotLong, formatSlotShort } from "./format";
import * as outbox from "./outbox";
import type { FlowContext } from "./types";

// Fluxo guiado por botoes/listas: caminho principal e deterministico para
// agendar, ver, cancelar e remarcar. Chama sempre as mesmas funcoes de
// src/booking/engine.ts que o agente de IA usa, para nunca haver divergencia
// de regras entre os dois caminhos. Todo texto vem de
// src/language/strings.ts (ctx.language) - nunca hardcoded aqui.

function ui(ctx: FlowContext) {
  return getUiStrings(ctx.language, ctx.business.defaultLanguage);
}

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
  const agent = await getAgent(ctx.business.id);
  const t = ui(ctx);
  await outbox.sendList(ctx, {
    bodyText: buildGreeting(ctx.business, agent, ctx.language),
    buttonText: t.menuButton,
    sections: [
      {
        title: t.menuSectionTitle,
        rows: [
          { id: REPLY.MENU_BOOK, title: t.menuRowBook },
          { id: REPLY.MENU_MY_BOOKINGS, title: t.menuRowMyBookings },
          { id: REPLY.MENU_CANCEL, title: t.menuRowCancel },
          { id: REPLY.MENU_HUMAN, title: t.menuRowHuman },
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
  const t = ui(ctx);
  const services = await prisma.service.findMany({
    where: { businessId: ctx.business.id, active: true },
    take: 10,
    orderBy: { name: "asc" },
  });

  if (services.length === 0) {
    await outbox.sendText(ctx, t.noServicesConfigured);
    return false;
  }

  await outbox.sendList(ctx, {
    bodyText: t.chooseServiceBody,
    buttonText: t.chooseServiceButton,
    sections: [
      {
        title: t.servicesSectionTitle,
        rows: services.map((s) => ({
          id: s.id,
          title: s.name.slice(0, 24),
          description: [formatPrice(s.price, ctx.business.currency, ctx.language), `${s.durationMinutes} min`]
            .filter(Boolean)
            .join(" - "),
        })),
      },
    ],
  });
  return true;
}

async function sendSlotList(ctx: FlowContext, serviceId: string): Promise<boolean> {
  const t = ui(ctx);
  const slots = await booking.getAvailableSlots(ctx.business.id, serviceId);
  if (slots.length === 0) {
    await outbox.sendText(ctx, t.noSlotsAvailable);
    return false;
  }

  await outbox.sendList(ctx, {
    bodyText: t.chooseSlotBody,
    buttonText: t.chooseSlotButton,
    sections: [
      {
        title: t.slotsSectionTitle,
        rows: slots.map((s) => ({
          id: s.start.toISOString(),
          // titulo de linha do WhatsApp tem limite de 24 caracteres -
          // mantido compacto/numerico independente do idioma.
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
  const t = ui(ctx);
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
          await outbox.sendText(ctx, t.noUpcomingBookings);
        } else {
          const lines = bookings.map((b) =>
            t.upcomingBookingLine(b.service.name, formatSlotLong(b.startsAt, ctx.business.timezone, ctx.language))
          );
          await outbox.sendText(ctx, lines.join("\n"));
        }
        await backToMenu(ctx, conversation.id);
        return;
      }

      if (replyId === REPLY.MENU_CANCEL) {
        const bookings = await booking.listUpcomingBookingsForCustomer(ctx.business.id, ctx.customer.id);
        if (bookings.length === 0) {
          await outbox.sendText(ctx, t.noUpcomingBookingsToChange);
          await backToMenu(ctx, conversation.id);
          return;
        }
        await outbox.sendList(ctx, {
          bodyText: t.chooseBookingToChangeBody,
          buttonText: t.chooseButton,
          sections: [
            {
              title: t.yourBookingsSectionTitle,
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
        await outbox.sendText(ctx, t.humanHandoffAck);
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
        t.confirmBooking(service.name, formatSlotLong(startsAt, ctx.business.timezone, ctx.language)),
        [
          { id: REPLY.CONFIRM_YES, title: t.confirmYes },
          { id: REPLY.CONFIRM_NO, title: t.confirmNo },
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
        await outbox.sendText(ctx, t.bookingNotConfirmed);
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
            t.bookingConfirmed(formatSlotLong(created.startsAt, ctx.business.timezone, ctx.language))
          );
          await backToMenu(ctx, conversation.id);
        } catch (err) {
          if (err instanceof BookingConflictError) {
            await outbox.sendText(ctx, t.slotTaken);
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
        t.whatToDoWithBooking(target.service.name, formatSlotLong(target.startsAt, ctx.business.timezone, ctx.language)),
        [
          { id: REPLY.ACTION_CANCEL, title: t.actionCancel },
          { id: REPLY.ACTION_RESCHEDULE, title: t.actionReschedule },
          { id: REPLY.ACTION_KEEP, title: t.actionKeep },
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
        await outbox.sendText(ctx, t.bookingCancelled);
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

      await outbox.sendText(ctx, t.bookingKept);
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
          t.bookingRescheduled(formatSlotLong(updated.startsAt, ctx.business.timezone, ctx.language))
        );
      } catch (err) {
        if (err instanceof BookingConflictError) {
          await outbox.sendText(ctx, t.rescheduleSlotTaken);
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
