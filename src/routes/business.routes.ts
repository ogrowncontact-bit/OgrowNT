import type { Role } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, currentUser, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";
import { logger } from "../logger";

const ROLES: Role[] = ["OWNER", "ADMIN", "STAFF"];

// requireAuth ja e aplicado no mount (/api/businesses) em server.ts.
export const businessRouter = Router();

// Lista as empresas as quais o usuario logado tem acesso (com o papel dele em
// cada uma) - e o que um futuro dashboard usaria para o seletor de empresa.
businessRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const user = currentUser(res);
    const memberships = await prisma.membership.findMany({
      where: { userId: user.id },
      include: { business: true },
    });
    res.json(
      memberships.map((m) => ({
        id: m.business.id,
        name: m.business.name,
        slug: m.business.slug,
        industry: m.business.industry,
        role: m.role,
      }))
    );
  })
);

// Adiciona um usuario JA CADASTRADO como membro da empresa com um papel.
// Sem convite por e-mail nesta fase - fora do escopo da Fundacao.
businessRouter.post(
  "/:businessId/members",
  requireMembership,
  requireRole("OWNER"),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { email, role } = req.body ?? {};

    if (!email || !role) {
      res.status(400).json({ error: "email e role sao obrigatorios." });
      return;
    }
    if (!ROLES.includes(role)) {
      res.status(400).json({ error: `role invalido. Use ${ROLES.join(", ")}.` });
      return;
    }

    const targetUser = await prisma.user.findUnique({
      where: { email: String(email).trim().toLowerCase() },
    });
    if (!targetUser) {
      res.status(404).json({
        error: "Nenhum usuario cadastrado com esse email. Peca para a pessoa criar uma conta primeiro.",
      });
      return;
    }

    const membership = await prisma.membership.upsert({
      where: { userId_businessId: { userId: targetUser.id, businessId: business.id } },
      update: { role: role as Role },
      create: { userId: targetUser.id, businessId: business.id, role: role as Role },
    });

    logger.info("business.member_added", { businessId: business.id, targetUserId: targetUser.id, role });
    res.status(201).json({ userId: targetUser.id, email: targetUser.email, role: membership.role });
  })
);
