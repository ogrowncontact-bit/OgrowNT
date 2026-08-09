import { Prisma, type Role } from "@prisma/client";
import { Router } from "express";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";

// Rotas de gestao de uma empresa (servicos, horarios, reservas, conversas).
// Montado em /api/businesses/:businessId (ver server.ts) - o :businessId vem
// do path de montagem, por isso mergeParams:true. requireAuth ja roda antes
// (aplicado no mount /api/businesses); aqui so falta confirmar o vinculo com
// ESSA empresa (requireMembership = isolamento multi-tenant) e o papel
// necessario para cada acao (requireRole).

export const adminRouter = Router({ mergeParams: true });

const WRITE_ROLES: Role[] = ["OWNER", "ADMIN"];

adminRouter.use(requireMembership);

adminRouter.get("/", (_req, res) => {
  const business = currentBusiness(res);
  res.json({ id: business.id, name: business.name, slug: business.slug, industry: business.industry, timezone: business.timezone });
});

adminRouter.get("/services", async (_req, res) => {
  const business = currentBusiness(res);
  const services = await prisma.service.findMany({ where: { businessId: business.id }, orderBy: { name: "asc" } });
  res.json(services);
});

adminRouter.post("/services", requireRole(...WRITE_ROLES), async (req, res) => {
  const business = currentBusiness(res);
  const { name, durationMinutes, price, active } = req.body ?? {};
  if (!name || !durationMinutes) {
    res.status(400).json({ error: "name e durationMinutes sao obrigatorios." });
    return;
  }
  const service = await prisma.service.create({
    data: {
      businessId: business.id,
      name: String(name),
      durationMinutes: Number(durationMinutes),
      price: price !== undefined && price !== null ? new Prisma.Decimal(price) : null,
      active: active ?? true,
    },
  });
  res.status(201).json(service);
});

adminRouter.patch("/services/:id", requireRole(...WRITE_ROLES), async (req, res) => {
  const business = currentBusiness(res);
  const existing = await prisma.service.findFirst({ where: { id: req.params.id, businessId: business.id } });
  if (!existing) {
    res.sendStatus(404);
    return;
  }
  const { name, durationMinutes, price, active } = req.body ?? {};
  const updated = await prisma.service.update({
    where: { id: existing.id },
    data: {
      ...(name !== undefined ? { name: String(name) } : {}),
      ...(durationMinutes !== undefined ? { durationMinutes: Number(durationMinutes) } : {}),
      ...(price !== undefined ? { price: price === null ? null : new Prisma.Decimal(price) } : {}),
      ...(active !== undefined ? { active: Boolean(active) } : {}),
    },
  });
  res.json(updated);
});

adminRouter.get("/business-hours", async (_req, res) => {
  const business = currentBusiness(res);
  const hours = await prisma.businessHours.findMany({
    where: { businessId: business.id },
    orderBy: { weekday: "asc" },
  });
  res.json(hours);
});

// Substitui o horario de funcionamento inteiro (mais simples e previsivel do
// que editar entradas individuais). Corpo esperado: array de
// { weekday: 0-6, openTime: "HH:mm", closeTime: "HH:mm" }.
adminRouter.put("/business-hours", requireRole(...WRITE_ROLES), async (req, res) => {
  const business = currentBusiness(res);
  const entries = Array.isArray(req.body) ? req.body : [];
  const valid = entries.every(
    (e: any) =>
      typeof e?.weekday === "number" &&
      e.weekday >= 0 &&
      e.weekday <= 6 &&
      typeof e?.openTime === "string" &&
      typeof e?.closeTime === "string"
  );
  if (!valid) {
    res.status(400).json({ error: "Corpo invalido. Esperado array de {weekday, openTime, closeTime}." });
    return;
  }

  await prisma.$transaction([
    prisma.businessHours.deleteMany({ where: { businessId: business.id } }),
    prisma.businessHours.createMany({
      data: entries.map((e: any) => ({
        businessId: business.id,
        weekday: e.weekday,
        openTime: e.openTime,
        closeTime: e.closeTime,
      })),
    }),
  ]);

  const hours = await prisma.businessHours.findMany({
    where: { businessId: business.id },
    orderBy: { weekday: "asc" },
  });
  res.json(hours);
});

adminRouter.get("/bookings", async (_req, res) => {
  const business = currentBusiness(res);
  const bookings = await prisma.booking.findMany({
    where: { businessId: business.id },
    include: { service: true, customer: true },
    orderBy: { startsAt: "desc" },
    take: 100,
  });
  res.json(bookings);
});

adminRouter.get("/conversations", async (req, res) => {
  const business = currentBusiness(res);
  const needsHumanParam = req.query.needsHuman;
  const needsHuman = needsHumanParam === "true" ? true : needsHumanParam === "false" ? false : undefined;

  const conversations = await prisma.conversation.findMany({
    where: { businessId: business.id, ...(needsHuman !== undefined ? { needsHuman } : {}) },
    include: { customer: true },
    orderBy: { lastMessageAt: "desc" },
    take: 100,
  });
  res.json(conversations);
});

// Devolve a conversa para o bot depois que um humano respondeu manualmente.
adminRouter.post("/conversations/:id/resolve", requireRole(...WRITE_ROLES), async (req, res) => {
  const business = currentBusiness(res);
  const conversation = await prisma.conversation.findFirst({
    where: { id: req.params.id, businessId: business.id },
  });
  if (!conversation) {
    res.sendStatus(404);
    return;
  }
  const updated = await prisma.conversation.update({
    where: { id: conversation.id },
    data: { needsHuman: false, step: "idle" },
  });
  res.json(updated);
});
