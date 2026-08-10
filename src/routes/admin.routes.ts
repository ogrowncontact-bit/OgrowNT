import { Prisma, type Role } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";
import { DETECTABLE_LANGUAGES } from "../language/detect";

const CURRENCY_CODE_PATTERN = /^[A-Z]{3}$/;

// Rotas de gestao de uma empresa (servicos, horarios, reservas, conversas).
// Montado em /api/businesses/:businessId (ver server.ts) - o :businessId vem
// do path de montagem, por isso mergeParams:true. requireAuth ja roda antes
// (aplicado no mount /api/businesses); aqui so falta confirmar o vinculo com
// ESSA empresa (requireMembership = isolamento multi-tenant) e o papel
// necessario para cada acao (requireRole). Todo handler async passa por
// asyncHandler (ver src/asyncHandler.ts) - sem isso, um erro dentro de um
// handler derruba o processo inteiro em vez de virar uma resposta 500.

export const adminRouter = Router({ mergeParams: true });

const WRITE_ROLES: Role[] = ["OWNER", "ADMIN"];

adminRouter.use(requireMembership);

adminRouter.get("/", (_req, res) => {
  const business = currentBusiness(res);
  res.json({
    id: business.id,
    name: business.name,
    slug: business.slug,
    industry: business.industry,
    timezone: business.timezone,
    description: business.description,
    address: business.address,
    phone: business.phone,
    metadata: business.metadata,
    defaultLanguage: business.defaultLanguage,
    supportedLanguages: business.supportedLanguages,
    currency: business.currency,
  });
});

// Edita o perfil da empresa (dados gerais + campos especificos do nicho em
// metadata - ver src/templates/registry.ts - + configuracao do motor
// multilingue: idiomas suportados/padrao e moeda).
adminRouter.patch(
  "/",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { name, description, address, phone, timezone, metadata, defaultLanguage, supportedLanguages, currency } =
      req.body ?? {};

    if (defaultLanguage !== undefined && !DETECTABLE_LANGUAGES.includes(defaultLanguage)) {
      res.status(400).json({ error: `defaultLanguage invalido. Valores aceitos: ${DETECTABLE_LANGUAGES.join(", ")}` });
      return;
    }
    if (supportedLanguages !== undefined) {
      const valid = Array.isArray(supportedLanguages) && supportedLanguages.every((l) => DETECTABLE_LANGUAGES.includes(l));
      if (!valid || supportedLanguages.length === 0) {
        res.status(400).json({ error: `supportedLanguages deve ser um array nao vazio com valores em: ${DETECTABLE_LANGUAGES.join(", ")}` });
        return;
      }
    }
    if (currency !== undefined && !CURRENCY_CODE_PATTERN.test(currency)) {
      res.status(400).json({ error: "currency deve ser um codigo ISO 4217 de 3 letras maiusculas (ex: BRL, USD, EUR)." });
      return;
    }

    const updated = await prisma.business.update({
      where: { id: business.id },
      data: {
        ...(name !== undefined ? { name: String(name) } : {}),
        ...(description !== undefined ? { description: description === null ? null : String(description) } : {}),
        ...(address !== undefined ? { address: address === null ? null : String(address) } : {}),
        ...(phone !== undefined ? { phone: phone === null ? null : String(phone) } : {}),
        ...(timezone !== undefined ? { timezone: String(timezone) } : {}),
        ...(metadata !== undefined ? { metadata: metadata as Prisma.InputJsonValue } : {}),
        ...(defaultLanguage !== undefined ? { defaultLanguage } : {}),
        ...(supportedLanguages !== undefined ? { supportedLanguages } : {}),
        ...(currency !== undefined ? { currency } : {}),
      },
    });
    res.json(updated);
  })
);

adminRouter.get(
  "/services",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const services = await prisma.service.findMany({ where: { businessId: business.id }, orderBy: { name: "asc" } });
    res.json(services);
  })
);

adminRouter.post(
  "/services",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { name, durationMinutes, price, active, metadata, requiresResourceType } = req.body ?? {};
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
        metadata: (metadata ?? {}) as Prisma.InputJsonValue,
        requiresResourceType: requiresResourceType ? String(requiresResourceType) : null,
      },
    });
    res.status(201).json(service);
  })
);

adminRouter.patch(
  "/services/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.service.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    const { name, durationMinutes, price, active, metadata, requiresResourceType } = req.body ?? {};
    const updated = await prisma.service.update({
      where: { id: existing.id },
      data: {
        ...(name !== undefined ? { name: String(name) } : {}),
        ...(durationMinutes !== undefined ? { durationMinutes: Number(durationMinutes) } : {}),
        ...(price !== undefined ? { price: price === null ? null : new Prisma.Decimal(price) } : {}),
        ...(active !== undefined ? { active: Boolean(active) } : {}),
        ...(metadata !== undefined ? { metadata: metadata as Prisma.InputJsonValue } : {}),
        ...(requiresResourceType !== undefined
          ? { requiresResourceType: requiresResourceType === null ? null : String(requiresResourceType) }
          : {}),
      },
    });
    res.json(updated);
  })
);

// --- Recursos (cavalo/mesa/quarto/instrutor - ver Resource no schema) ---

adminRouter.get(
  "/resources",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const type = typeof req.query.type === "string" ? req.query.type : undefined;
    const resources = await prisma.resource.findMany({
      where: { businessId: business.id, ...(type ? { type } : {}) },
      orderBy: { name: "asc" },
    });
    res.json(resources);
  })
);

adminRouter.post(
  "/resources",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { type, name, capacity, active, metadata } = req.body ?? {};
    if (!type || !name) {
      res.status(400).json({ error: "type e name sao obrigatorios." });
      return;
    }
    const resource = await prisma.resource.create({
      data: {
        businessId: business.id,
        type: String(type),
        name: String(name),
        capacity: capacity !== undefined ? Number(capacity) : 1,
        active: active ?? true,
        metadata: (metadata ?? {}) as Prisma.InputJsonValue,
      },
    });
    res.status(201).json(resource);
  })
);

adminRouter.patch(
  "/resources/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.resource.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    const { type, name, capacity, active, metadata } = req.body ?? {};
    const updated = await prisma.resource.update({
      where: { id: existing.id },
      data: {
        ...(type !== undefined ? { type: String(type) } : {}),
        ...(name !== undefined ? { name: String(name) } : {}),
        ...(capacity !== undefined ? { capacity: Number(capacity) } : {}),
        ...(active !== undefined ? { active: Boolean(active) } : {}),
        ...(metadata !== undefined ? { metadata: metadata as Prisma.InputJsonValue } : {}),
      },
    });
    res.json(updated);
  })
);

adminRouter.delete(
  "/resources/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.resource.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    await prisma.resource.delete({ where: { id: existing.id } });
    res.sendStatus(204);
  })
);

// --- Campos de reserva customizados (ver CustomBookingField no schema) ---

const FIELD_TYPES = ["TEXT", "NUMBER", "BOOLEAN", "SELECT"];

adminRouter.get(
  "/custom-fields",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const serviceId = typeof req.query.serviceId === "string" ? req.query.serviceId : undefined;
    const fields = await prisma.customBookingField.findMany({
      where: { businessId: business.id, ...(serviceId ? { serviceId } : {}) },
      orderBy: { createdAt: "asc" },
    });
    res.json(fields);
  })
);

adminRouter.post(
  "/custom-fields",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { serviceId, label, fieldType, options, required } = req.body ?? {};

    if (!label || !fieldType || !FIELD_TYPES.includes(fieldType)) {
      res.status(400).json({ error: `label obrigatorio e fieldType deve ser um de: ${FIELD_TYPES.join(", ")}` });
      return;
    }
    if (serviceId) {
      const service = await prisma.service.findFirst({ where: { id: serviceId, businessId: business.id } });
      if (!service) {
        res.status(404).json({ error: "serviceId nao encontrado nesta empresa." });
        return;
      }
    }

    const field = await prisma.customBookingField.create({
      data: {
        businessId: business.id,
        serviceId: serviceId ?? null,
        label: String(label),
        fieldType,
        options: Array.isArray(options) ? options.map(String) : [],
        required: Boolean(required),
      },
    });
    res.status(201).json(field);
  })
);

adminRouter.delete(
  "/custom-fields/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.customBookingField.findFirst({
      where: { id: req.params.id, businessId: business.id },
    });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    await prisma.customBookingField.delete({ where: { id: existing.id } });
    res.sendStatus(204);
  })
);

adminRouter.get(
  "/business-hours",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const hours = await prisma.businessHours.findMany({
      where: { businessId: business.id },
      orderBy: { weekday: "asc" },
    });
    res.json(hours);
  })
);

// Substitui o horario de funcionamento inteiro (mais simples e previsivel do
// que editar entradas individuais). Corpo esperado: array de
// { weekday: 0-6, openTime: "HH:mm", closeTime: "HH:mm" }.
adminRouter.put(
  "/business-hours",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
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
  })
);

adminRouter.get(
  "/bookings",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const bookings = await prisma.booking.findMany({
      where: { businessId: business.id },
      include: { service: true, customer: true },
      orderBy: { startsAt: "desc" },
      take: 100,
    });
    res.json(bookings);
  })
);

adminRouter.get(
  "/conversations",
  asyncHandler(async (req, res) => {
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
  })
);

// Devolve a conversa para o bot depois que um humano respondeu manualmente.
adminRouter.post(
  "/conversations/:id/resolve",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
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
  })
);
