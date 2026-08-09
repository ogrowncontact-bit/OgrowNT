import type Anthropic from "@anthropic-ai/sdk";
import { prisma } from "../db";
import * as booking from "../booking/engine";
import { BookingConflictError, NotFoundError } from "../booking/errors";
import { formatPrice, formatSlotShort } from "../conversation/format";
import type { FlowContext } from "../conversation/types";

// Ferramentas do agente de IA - espelham exatamente as capacidades do fluxo
// guiado, chamando o mesmo motor de reservas (src/booking/engine.ts). O
// businessId/customerId vem sempre do FlowContext (nunca do modelo), entao o
// agente so consegue ler/agir dentro do tenant e do cliente da conversa atual.

const WEEKDAY_NAMES = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"];

export function buildToolDefinitions(): Anthropic.Tool[] {
  return [
    {
      name: "list_business_info",
      description:
        "Retorna nome, fuso horario e horario de funcionamento da empresa. Use para responder perguntas sobre quando a empresa abre ou fecha.",
      input_schema: { type: "object", properties: {} },
    },
    {
      name: "list_services",
      description:
        "Lista os servicos ativos oferecidos pela empresa, com id, nome, duracao e preco. Use o id retornado aqui para chamar check_availability ou create_booking.",
      input_schema: { type: "object", properties: {} },
    },
    {
      name: "check_availability",
      description: "Retorna os proximos horarios livres para um servico especifico.",
      input_schema: {
        type: "object",
        properties: { serviceId: { type: "string" } },
        required: ["serviceId"],
      },
    },
    {
      name: "create_booking",
      description:
        "Cria (confirma) um agendamento para o cliente atual num servico e horario especificos. So chame depois que o cliente confirmar explicitamente o horario escolhido.",
      input_schema: {
        type: "object",
        properties: {
          serviceId: { type: "string" },
          startsAtIso: {
            type: "string",
            description: "Data/hora ISO 8601 do horario escolhido, exatamente como retornado por check_availability.",
          },
        },
        required: ["serviceId", "startsAtIso"],
      },
    },
    {
      name: "list_my_bookings",
      description: "Lista os agendamentos futuros do cliente atual.",
      input_schema: { type: "object", properties: {} },
    },
    {
      name: "cancel_booking",
      description: "Cancela um agendamento existente do cliente atual.",
      input_schema: {
        type: "object",
        properties: { bookingId: { type: "string" } },
        required: ["bookingId"],
      },
    },
    {
      name: "reschedule_booking",
      description: "Move um agendamento existente do cliente atual para um novo horario.",
      input_schema: {
        type: "object",
        properties: {
          bookingId: { type: "string" },
          newStartsAtIso: { type: "string" },
        },
        required: ["bookingId", "newStartsAtIso"],
      },
    },
    {
      name: "request_human",
      description:
        "Encaminha a conversa para um atendente humano e para as respostas automaticas do bot. Use quando o cliente pedir explicitamente para falar com uma pessoa, ou quando voce nao conseguir ajudar com seguranca.",
      input_schema: { type: "object", properties: {} },
    },
  ];
}

export function createToolExecutor(ctx: FlowContext) {
  return async function executeTool(name: string, input: Record<string, unknown>): Promise<string> {
    try {
      switch (name) {
        case "list_business_info": {
          const hours = await prisma.businessHours.findMany({
            where: { businessId: ctx.business.id },
            orderBy: { weekday: "asc" },
          });
          return JSON.stringify({
            name: ctx.business.name,
            timezone: ctx.business.timezone,
            hours: hours.map((h) => `${WEEKDAY_NAMES[h.weekday]}: ${h.openTime}-${h.closeTime}`),
          });
        }

        case "list_services": {
          const services = await prisma.service.findMany({
            where: { businessId: ctx.business.id, active: true },
          });
          return JSON.stringify(
            services.map((s) => ({
              id: s.id,
              name: s.name,
              durationMinutes: s.durationMinutes,
              price: formatPrice(s.price),
            }))
          );
        }

        case "check_availability": {
          const slots = await booking.getAvailableSlots(ctx.business.id, String(input.serviceId ?? ""));
          return JSON.stringify(
            slots.map((s) => ({
              startsAtIso: s.start.toISOString(),
              label: formatSlotShort(s.start, ctx.business.timezone),
            }))
          );
        }

        case "create_booking": {
          const created = await booking.createBooking({
            businessId: ctx.business.id,
            customerId: ctx.customer.id,
            serviceId: String(input.serviceId ?? ""),
            startsAt: new Date(String(input.startsAtIso ?? "")),
          });
          return JSON.stringify({
            ok: true,
            bookingId: created.id,
            startsAtIso: created.startsAt.toISOString(),
            label: formatSlotShort(created.startsAt, ctx.business.timezone),
          });
        }

        case "list_my_bookings": {
          const bookings = await booking.listUpcomingBookingsForCustomer(ctx.business.id, ctx.customer.id);
          return JSON.stringify(
            bookings.map((b) => ({
              bookingId: b.id,
              service: b.service.name,
              startsAtIso: b.startsAt.toISOString(),
              label: formatSlotShort(b.startsAt, ctx.business.timezone),
            }))
          );
        }

        case "cancel_booking": {
          const updated = await booking.cancelBooking(ctx.business.id, String(input.bookingId ?? ""));
          return JSON.stringify({ ok: true, bookingId: updated.id, status: updated.status });
        }

        case "reschedule_booking": {
          const updated = await booking.rescheduleBooking(
            ctx.business.id,
            String(input.bookingId ?? ""),
            new Date(String(input.newStartsAtIso ?? ""))
          );
          return JSON.stringify({
            ok: true,
            bookingId: updated.id,
            startsAtIso: updated.startsAt.toISOString(),
            label: formatSlotShort(updated.startsAt, ctx.business.timezone),
          });
        }

        case "request_human": {
          await prisma.conversation.update({
            where: { id: ctx.conversationId },
            data: { needsHuman: true },
          });
          return JSON.stringify({ ok: true });
        }

        default:
          return JSON.stringify({ error: `Ferramenta desconhecida: ${name}` });
      }
    } catch (err) {
      if (err instanceof BookingConflictError || err instanceof NotFoundError) {
        return JSON.stringify({ error: err.message });
      }
      throw err;
    }
  };
}
