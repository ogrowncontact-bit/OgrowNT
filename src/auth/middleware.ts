import type { Business, Role, User } from "@prisma/client";
import type { NextFunction, Request, Response } from "express";
import { prisma } from "../db";
import { verifyAccessToken } from "./tokens";

// requireAuth -> quem e o usuario (JWT).
// requireMembership -> ele tem acesso a ESSA empresa (:businessId da rota)?
//   Este e o mecanismo de isolamento multi-tenant: nenhuma rota de negocio
//   roda sem passar por aqui.
// requireRole -> ele tem permissao para ESSA acao dentro da empresa?

export async function requireAuth(req: Request, res: Response, next: NextFunction): Promise<void> {
  const header = req.header("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) {
    res.status(401).json({ error: "Token de autenticacao ausente." });
    return;
  }

  try {
    const { userId } = verifyAccessToken(token);
    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      res.status(401).json({ error: "Token invalido." });
      return;
    }
    res.locals.userId = user.id;
    res.locals.user = user;
    next();
  } catch {
    res.status(401).json({ error: "Token invalido ou expirado." });
  }
}

export async function requireMembership(req: Request, res: Response, next: NextFunction): Promise<void> {
  const businessId = req.params.businessId;
  const userId = res.locals.userId as string | undefined;
  if (!businessId || !userId) {
    res.sendStatus(400);
    return;
  }

  const membership = await prisma.membership.findUnique({
    where: { userId_businessId: { userId, businessId } },
  });
  if (!membership) {
    res.status(403).json({ error: "Voce nao tem acesso a essa empresa." });
    return;
  }

  const business = await prisma.business.findUnique({ where: { id: businessId } });
  if (!business) {
    res.sendStatus(404);
    return;
  }

  res.locals.business = business;
  res.locals.role = membership.role;
  next();
}

export function requireRole(...allowed: Role[]) {
  return (_req: Request, res: Response, next: NextFunction): void => {
    const role = res.locals.role as Role | undefined;
    if (!role || !allowed.includes(role)) {
      res.status(403).json({ error: "Voce nao tem permissao para essa acao." });
      return;
    }
    next();
  };
}

export function currentUser(res: Response): User {
  return res.locals.user as User;
}

export function currentBusiness(res: Response): Business {
  return res.locals.business as Business;
}

export function currentRole(res: Response): Role {
  return res.locals.role as Role;
}
