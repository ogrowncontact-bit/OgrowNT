import type Anthropic from "@anthropic-ai/sdk";
import { KnowledgeCategory, Prisma } from "@prisma/client";
import { prisma } from "../db";
import * as booking from "../booking/engine";
import { BookingConflictError, NotFoundError } from "../booking/errors";
import { formatPrice, formatSlotLong } from "../conversation/format";
import type { FlowContext } from "../conversation/types";

// Ferramentas do agente de IA - espelham exatamente as capacidades do fluxo
// guiado, chamando o mesmo motor de reservas (src/booking/engine.ts). O
// businessId/customerId vem sempre do FlowContext (nunca do modelo), entao o
// agente so consegue ler/agir dentro do tenant e do cliente da conversa atual.

const WEEKDAY_NAMES = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"];
const KNOWLEDGE_CATEGORIES = Object.values(KnowledgeCategory);

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
        "Lista os servicos ativos oferecidos pela empresa, com id, nome, duracao, preco e quais perguntas extras (customFields) fazer antes de reservar cada um. Use o id retornado aqui para chamar check_availability ou create_booking.",
      input_schema: { type: "object", properties: {} },
    },
    {
      name: "check_availability",
      description:
        "Retorna os proximos horarios livres para um servico especifico. Informe quantity se o cliente ja disse para quantas pessoas/unidades e (nao pergunte de novo se ja souber).",
      input_schema: {
        type: "object",
        properties: {
          serviceId: { type: "string" },
          quantity: { type: "number", description: "Numero de pessoas/unidades. Padrao 1." },
        },
        required: ["serviceId"],
      },
    },
    {
      name: "create_booking",
      description:
        "Cria (confirma) um agendamento para o cliente atual num servico e horario especificos. So chame depois que o cliente confirmar explicitamente o horario escolhido E depois de coletar as respostas dos customFields obrigatorios desse servico (retornados por list_services), colocando-as em metadata.",
      input_schema: {
        type: "object",
        properties: {
          serviceId: { type: "string" },
          startsAtIso: {
            type: "string",
            description: "Data/hora ISO 8601 do horario escolhido, exatamente como retornado por check_availability.",
          },
          quantity: { type: "number", description: "Numero de pessoas/unidades. Padrao 1." },
          notes: { type: "string", description: "Observacoes livres do cliente sobre a reserva." },
          metadata: {
            type: "object",
            description: "Respostas dos customFields do servico, no formato { chaveDoCampo: valor }.",
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
    {
      name: "search_knowledge",
      description:
        "Busca na base de conhecimento da empresa (politicas, FAQ, localizacao, regras, documentos, etc). Use antes de responder qualquer pergunta sobre a empresa que voce nao tenha certeza absoluta - nunca invente politicas ou informacoes.",
      input_schema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Palavras-chave para buscar, ex: 'cancelamento', 'animais de estimacao'." },
          category: { type: "string", enum: KNOWLEDGE_CATEGORIES, description: "Filtra por categoria, se souber qual." },
        },
      },
    },
  ];
}

async function logToolCall(
  ctx: FlowContext,
  toolName: string,
  input: Record<string, unknown>,
  success: boolean
): Promise<void> {
  try {
    await prisma.toolCallLog.create({
      data: {
        businessId: ctx.business.id,
        conversationId: ctx.conversationId,
        toolName,
        input: input as Prisma.InputJsonValue,
        success,
      },
    });
  } catch (err) {
    // Observabilidade nunca deve derrubar o atendimento - so loga no console.
    console.error("[ai] falha ao registrar ToolCallLog:", err);
  }
}

// Registra toda chamada de ferramenta (nome, input, sucesso) para
// observabilidade (secao "Tool Execution"). "Sucesso" aqui significa que a
// ferramenta rodou e devolveu uma resposta (mesmo que a resposta seja um erro
// de negocio, como horario indisponivel) - so marca falha quando algo
// realmente inesperado acontece.
export function createToolExecutor(ctx: FlowContext) {
  return async function executeTool(name: string, input: Record<string, unknown>): Promise<string> {
    try {
      const result = await runTool(ctx, name, input);
      await logToolCall(ctx, name, input, true);
      return result;
    } catch (err) {
      await logToolCall(ctx, name, input, false);
      throw err;
    }
  };
}

async function runTool(ctx: FlowContext, name: string, input: Record<string, unknown>): Promise<string> {
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
          const fields = await prisma.customBookingField.findMany({
            where: { businessId: ctx.business.id },
          });
          return JSON.stringify(
            services.map((s) => ({
              id: s.id,
              name: s.name,
              durationMinutes: s.durationMinutes,
              price: formatPrice(s.price, ctx.business.currency, ctx.language),
              customFields: fields
                .filter((f) => f.serviceId === null || f.serviceId === s.id)
                .map((f) => ({
                  key: f.id,
                  label: f.label,
                  type: f.fieldType,
                  options: f.options,
                  required: f.required,
                })),
            }))
          );
        }

        case "check_availability": {
          const quantity = typeof input.quantity === "number" ? input.quantity : undefined;
          const slots = await booking.getAvailableSlots(ctx.business.id, String(input.serviceId ?? ""), { quantity });
          return JSON.stringify(
            slots.map((s) => ({
              startsAtIso: s.start.toISOString(),
              label: formatSlotLong(s.start, ctx.business.timezone, ctx.language),
            }))
          );
        }

        case "create_booking": {
          const quantity = typeof input.quantity === "number" ? input.quantity : undefined;
          const notes = typeof input.notes === "string" ? input.notes : undefined;
          const metadata =
            input.metadata && typeof input.metadata === "object" ? (input.metadata as Record<string, unknown>) : undefined;

          const created = await booking.createBooking({
            businessId: ctx.business.id,
            customerId: ctx.customer.id,
            serviceId: String(input.serviceId ?? ""),
            startsAt: new Date(String(input.startsAtIso ?? "")),
            quantity,
            notes,
            metadata,
          });
          return JSON.stringify({
            ok: true,
            bookingId: created.id,
            startsAtIso: created.startsAt.toISOString(),
            label: formatSlotLong(created.startsAt, ctx.business.timezone, ctx.language),
          });
        }

        case "list_my_bookings": {
          const bookings = await booking.listUpcomingBookingsForCustomer(ctx.business.id, ctx.customer.id);
          return JSON.stringify(
            bookings.map((b) => ({
              bookingId: b.id,
              service: b.service.name,
              startsAtIso: b.startsAt.toISOString(),
              label: formatSlotLong(b.startsAt, ctx.business.timezone, ctx.language),
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
            label: formatSlotLong(updated.startsAt, ctx.business.timezone, ctx.language),
          });
        }

        case "request_human": {
          await prisma.conversation.update({
            where: { id: ctx.conversationId },
            data: { needsHuman: true },
          });
          return JSON.stringify({ ok: true });
        }

        case "search_knowledge": {
          const query = typeof input.query === "string" ? input.query.trim() : "";
          const categoryInput = typeof input.category === "string" ? input.category : undefined;
          const category = KNOWLEDGE_CATEGORIES.includes(categoryInput as KnowledgeCategory)
            ? (categoryInput as KnowledgeCategory)
            : undefined;

          const entries = await prisma.knowledgeEntry.findMany({
            where: {
              businessId: ctx.business.id,
              ...(category ? { category } : {}),
              ...(query
                ? {
                    OR: [
                      { title: { contains: query, mode: "insensitive" } },
                      { content: { contains: query, mode: "insensitive" } },
                    ],
                  }
                : {}),
            },
            take: 5,
          });

          if (entries.length === 0) {
            return JSON.stringify({
              found: false,
              message: "Nenhuma informacao encontrada na base de conhecimento para essa busca.",
            });
          }
          return JSON.stringify({
            found: true,
            entries: entries.map((e) => ({ category: e.category, title: e.title, content: e.content })),
          });
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
}
