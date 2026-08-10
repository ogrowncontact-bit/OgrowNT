import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership } from "../auth/middleware";
import { prisma } from "../db";

// Rota de metricas do dashboard (Fase 8) - so agregacoes de leitura sobre o
// que ja existe no banco (conversas, bookings, ToolCallLog); nenhuma tabela
// nova. Montado em /api/businesses/:businessId (ver server.ts).
export const metricsRouter = Router({ mergeParams: true });

metricsRouter.use(requireMembership);

const DEFAULT_DAYS = 30;
const MIN_DAYS = 1;
const MAX_DAYS = 365;

function parseDays(raw: unknown): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return DEFAULT_DAYS;
  return Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.round(parsed)));
}

metricsRouter.get(
  "/metrics",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const days = parseDays(req.query.days);
    const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    const now = new Date();

    const [
      conversationsTotal,
      conversationsAiResolved,
      conversationsNeedingHumanNow,
      bookingsByStatusRaw,
      upcomingBookings,
      topServicesRaw,
      toolCallsTotal,
      toolCallsSuccess,
      messagesIn,
      messagesOut,
    ] = await Promise.all([
      prisma.conversation.count({ where: { businessId: business.id, lastMessageAt: { gte: since } } }),
      // "Resolvida pela IA" = nenhuma mensagem HUMAN nessa conversa - ou seja,
      // nenhum atendente precisou intervir (ver ConversationThread/Fase 7).
      prisma.conversation.count({
        where: { businessId: business.id, lastMessageAt: { gte: since }, messages: { none: { sender: "HUMAN" } } },
      }),
      prisma.conversation.count({ where: { businessId: business.id, needsHuman: true } }),
      prisma.booking.groupBy({
        by: ["status"],
        where: { businessId: business.id, createdAt: { gte: since } },
        _count: { _all: true },
      }),
      prisma.booking.count({ where: { businessId: business.id, status: "CONFIRMED", startsAt: { gte: now } } }),
      prisma.booking.groupBy({
        by: ["serviceId"],
        where: { businessId: business.id, createdAt: { gte: since } },
        _count: { _all: true },
        orderBy: { _count: { serviceId: "desc" } },
        take: 5,
      }),
      prisma.toolCallLog.count({ where: { businessId: business.id, createdAt: { gte: since } } }),
      prisma.toolCallLog.count({ where: { businessId: business.id, createdAt: { gte: since }, success: true } }),
      prisma.message.count({ where: { conversation: { businessId: business.id }, direction: "IN", createdAt: { gte: since } } }),
      prisma.message.count({ where: { conversation: { businessId: business.id }, direction: "OUT", createdAt: { gte: since } } }),
    ]);

    const services = await prisma.service.findMany({
      where: { id: { in: topServicesRaw.map((s) => s.serviceId) } },
      select: { id: true, name: true },
    });
    const serviceNameById = new Map(services.map((s) => [s.id, s.name]));

    const bookingsByStatus = { PENDING: 0, CONFIRMED: 0, CANCELLED: 0, COMPLETED: 0, NO_SHOW: 0 } as Record<string, number>;
    let bookingsTotal = 0;
    for (const row of bookingsByStatusRaw) {
      bookingsByStatus[row.status] = row._count._all;
      bookingsTotal += row._count._all;
    }

    res.json({
      period: { days, since: since.toISOString() },
      conversations: {
        total: conversationsTotal,
        aiResolved: conversationsAiResolved,
        aiResolvedRate: conversationsTotal > 0 ? conversationsAiResolved / conversationsTotal : null,
        needingHumanNow: conversationsNeedingHumanNow,
      },
      bookings: {
        total: bookingsTotal,
        byStatus: bookingsByStatus,
        upcomingConfirmed: upcomingBookings,
      },
      topServices: topServicesRaw.map((s) => ({
        serviceId: s.serviceId,
        name: serviceNameById.get(s.serviceId) ?? "Servico removido",
        bookings: s._count._all,
      })),
      toolCalls: {
        total: toolCallsTotal,
        successRate: toolCallsTotal > 0 ? toolCallsSuccess / toolCallsTotal : null,
      },
      messages: {
        in: messagesIn,
        out: messagesOut,
      },
    });
  })
);
