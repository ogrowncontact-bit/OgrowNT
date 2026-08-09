import { randomBytes } from "node:crypto";
import { BusinessIndustry } from "@prisma/client";
import { Router } from "express";
import rateLimit from "express-rate-limit";
import { currentUser, requireAuth } from "../auth/middleware";
import { hashPassword, verifyPassword } from "../auth/passwords";
import { signAccessToken } from "../auth/tokens";
import { prisma } from "../db";
import { logger } from "../logger";

// Rotas publicas de autenticacao. /register cria, num unico passo, o User +
// a Business (com o nicho escolhido) + a Membership(OWNER) - cobre "criar
// conta" + "escolher nicho" do fluxo de onboarding.
export const authRouter = Router();

const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Muitas tentativas de login. Tente novamente em alguns minutos." },
});

function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 60);
}

async function generateUniqueSlug(name: string): Promise<string> {
  const base = slugify(name) || "empresa";
  const existing = await prisma.business.findUnique({ where: { slug: base } });
  if (!existing) return base;
  return `${base}-${randomBytes(3).toString("hex")}`;
}

authRouter.post("/register", async (req, res) => {
  const { email, password, name, businessName, industry } = req.body ?? {};

  if (!email || !password || !name || !businessName || !industry) {
    res.status(400).json({ error: "email, password, name, businessName e industry sao obrigatorios." });
    return;
  }
  if (!Object.values(BusinessIndustry).includes(industry)) {
    res.status(400).json({
      error: `industry invalido. Valores aceitos: ${Object.values(BusinessIndustry).join(", ")}`,
    });
    return;
  }
  if (String(password).length < 8) {
    res.status(400).json({ error: "A senha precisa ter pelo menos 8 caracteres." });
    return;
  }

  const normalizedEmail = String(email).trim().toLowerCase();
  const existingUser = await prisma.user.findUnique({ where: { email: normalizedEmail } });
  if (existingUser) {
    res.status(409).json({ error: "Ja existe uma conta com esse email." });
    return;
  }

  const passwordHash = await hashPassword(String(password));
  const slug = await generateUniqueSlug(String(businessName));

  const result = await prisma.$transaction(async (tx) => {
    const user = await tx.user.create({
      data: { email: normalizedEmail, passwordHash, name: String(name) },
    });
    const business = await tx.business.create({
      data: { name: String(businessName), slug, industry: industry as BusinessIndustry },
    });
    await tx.membership.create({
      data: { userId: user.id, businessId: business.id, role: "OWNER" },
    });
    return { user, business };
  });

  logger.info("auth.register", { userId: result.user.id, businessId: result.business.id, industry });

  const token = signAccessToken({ userId: result.user.id });
  res.status(201).json({
    token,
    user: { id: result.user.id, email: result.user.email, name: result.user.name },
    business: {
      id: result.business.id,
      name: result.business.name,
      slug: result.business.slug,
      industry: result.business.industry,
    },
  });
});

authRouter.post("/login", loginLimiter, async (req, res) => {
  const { email, password } = req.body ?? {};
  if (!email || !password) {
    res.status(400).json({ error: "email e password sao obrigatorios." });
    return;
  }

  const normalizedEmail = String(email).trim().toLowerCase();
  const user = await prisma.user.findUnique({ where: { email: normalizedEmail } });
  if (!user) {
    logger.warn("auth.login_failed", { email: normalizedEmail, reason: "not_found" });
    res.status(401).json({ error: "Email ou senha invalidos." });
    return;
  }

  const valid = await verifyPassword(String(password), user.passwordHash);
  if (!valid) {
    logger.warn("auth.login_failed", { userId: user.id, reason: "bad_password" });
    res.status(401).json({ error: "Email ou senha invalidos." });
    return;
  }

  const token = signAccessToken({ userId: user.id });
  logger.info("auth.login", { userId: user.id });
  res.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

authRouter.get("/me", requireAuth, async (_req, res) => {
  const user = currentUser(res);
  const memberships = await prisma.membership.findMany({
    where: { userId: user.id },
    include: { business: { select: { id: true, name: true, slug: true, industry: true } } },
  });
  res.json({
    user: { id: user.id, email: user.email, name: user.name },
    memberships: memberships.map((m) => ({ role: m.role, business: m.business })),
  });
});
