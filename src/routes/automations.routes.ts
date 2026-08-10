import { Prisma, type AutomationTrigger, type Role } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";

// CRUD de automacoes proativas por empresa (Fase 9 - ver Automation no
// schema e src/automations/scheduler.ts). So o gatilho/offset sao
// configuraveis aqui - o texto da mensagem vem de um template do WhatsApp
// pre-aprovado, global por tipo (ver src/config.ts), porque o WhatsApp nao
// permite texto livre fora da janela de 24h de conversa.
export const automationsRouter = Router({ mergeParams: true });

automationsRouter.use(requireMembership);

const WRITE_ROLES: Role[] = ["OWNER", "ADMIN"];
const TRIGGERS: AutomationTrigger[] = ["BOOKING_REMINDER", "BOOKING_FOLLOWUP"];
const MIN_OFFSET_MINUTES = 0;
const MAX_OFFSET_MINUTES = 60 * 24 * 30; // 30 dias

function isValidOffset(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= MIN_OFFSET_MINUTES && value <= MAX_OFFSET_MINUTES;
}

automationsRouter.get(
  "/automations",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const automations = await prisma.automation.findMany({
      where: { businessId: business.id },
      orderBy: [{ trigger: "asc" }, { offsetMinutes: "asc" }],
    });
    res.json(automations);
  })
);

automationsRouter.post(
  "/automations",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { trigger, offsetMinutes, active } = req.body ?? {};

    if (!TRIGGERS.includes(trigger)) {
      res.status(400).json({ error: `trigger invalido. Use ${TRIGGERS.join(" ou ")}.` });
      return;
    }
    if (!isValidOffset(offsetMinutes)) {
      res.status(400).json({ error: `offsetMinutes deve ser um inteiro entre ${MIN_OFFSET_MINUTES} e ${MAX_OFFSET_MINUTES}.` });
      return;
    }

    try {
      const automation = await prisma.automation.create({
        data: { businessId: business.id, trigger, offsetMinutes, active: active ?? true },
      });
      res.status(201).json(automation);
    } catch (err) {
      if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002") {
        res.status(409).json({ error: "Ja existe uma automacao desse tipo com esse offset." });
        return;
      }
      throw err;
    }
  })
);

automationsRouter.patch(
  "/automations/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.automation.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }

    const { active, offsetMinutes } = req.body ?? {};
    if (offsetMinutes !== undefined && !isValidOffset(offsetMinutes)) {
      res.status(400).json({ error: `offsetMinutes deve ser um inteiro entre ${MIN_OFFSET_MINUTES} e ${MAX_OFFSET_MINUTES}.` });
      return;
    }

    try {
      const updated = await prisma.automation.update({
        where: { id: existing.id },
        data: {
          ...(active !== undefined ? { active: Boolean(active) } : {}),
          ...(offsetMinutes !== undefined ? { offsetMinutes } : {}),
        },
      });
      res.json(updated);
    } catch (err) {
      if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002") {
        res.status(409).json({ error: "Ja existe uma automacao desse tipo com esse offset." });
        return;
      }
      throw err;
    }
  })
);

automationsRouter.delete(
  "/automations/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.automation.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    await prisma.automation.delete({ where: { id: existing.id } });
    res.sendStatus(204);
  })
);
