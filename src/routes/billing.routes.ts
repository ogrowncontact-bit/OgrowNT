import type { Role } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { BillingNotImplementedError } from "../billing/errors";
import { prisma } from "../db";

// Planos (Fase 10) - tabela publica, sem autenticacao: uma pagina de precos
// futura consegue listar antes mesmo do usuario criar conta. Preco vive no
// banco (Plan), nunca hardcoded no codigo.
export const plansRouter = Router();

plansRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const plans = await prisma.plan.findMany({ where: { active: true }, orderBy: { priceMonthly: "asc" } });
    res.json(plans);
  })
);

// Assinatura de uma empresa especifica (Fase 10). Montado em
// /api/businesses/:businessId (ver server.ts). NAO ha processador de
// pagamento real integrado nesta versao - setupFeePaid/status sao
// alterados manualmente pelo time (ver scripts/mark-subscription-paid.ts)
// depois de receber o pagamento fora do sistema; a rota de checkout e um
// stub honesto (501), nao finge cobrar ninguem.
export const billingRouter = Router({ mergeParams: true });

billingRouter.use(requireMembership);

const WRITE_ROLES: Role[] = ["OWNER"];

billingRouter.get(
  "/subscription",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const subscription = await prisma.subscription.findUnique({
      where: { businessId: business.id },
      include: { plan: true },
    });
    if (!subscription) {
      res.sendStatus(404);
      return;
    }
    res.json(subscription);
  })
);

billingRouter.post(
  "/subscription/plan",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { planKey } = req.body ?? {};

    const plan = await prisma.plan.findUnique({ where: { key: String(planKey ?? "") } });
    if (!plan || !plan.active) {
      res.status(400).json({ error: "planKey invalido." });
      return;
    }

    const existing = await prisma.subscription.findUnique({ where: { businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }

    const updated = await prisma.subscription.update({
      where: { businessId: business.id },
      data: { planId: plan.id },
      include: { plan: true },
    });
    res.json(updated);
  })
);

// Stub honesto - ver src/billing/errors.ts. Nenhuma cobrança acontece aqui.
billingRouter.post(
  "/subscription/checkout",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (_req, res) => {
    const err = new BillingNotImplementedError("Pagamento online");
    res.status(501).json({ error: err.message });
  })
);
