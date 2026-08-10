import { AgentTone, EmojiUsage, Formality, KnowledgeCategory, type Role } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";

// Rotas de "Agent Core": identidade/voz do agente (Agent), base de
// conhecimento (KnowledgeEntry) e regras de negocio (BusinessRule) - o que
// src/ai/identity.ts e src/ai/tools.ts consultam para montar o prompt e
// responder perguntas. Autocontido (roda sua propria requireMembership).
export const agentRouter = Router({ mergeParams: true });

const WRITE_ROLES: Role[] = ["OWNER", "ADMIN"];
const TONES = Object.values(AgentTone);
const FORMALITIES = Object.values(Formality);
const EMOJI_LEVELS = Object.values(EmojiUsage);
const KNOWLEDGE_CATEGORIES = Object.values(KnowledgeCategory);

const MAX_SHORT_TEXT = 1000; // greetingMessage / instructions / rule description
const MAX_TITLE_LENGTH = 200;
const MAX_CONTENT_LENGTH = 5000;

agentRouter.use(requireMembership);

// --- Identidade do agente ---

agentRouter.get(
  "/agent",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const agent = await prisma.agent.findUnique({ where: { businessId: business.id } });
    // null = empresa ainda nao configurou; o sistema usa um padrao neutro nesse caso.
    res.json(agent);
  })
);

agentRouter.put(
  "/agent",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { name, tone, formality, emojiUsage, greetingMessage, instructions, active } = req.body ?? {};

    if (tone !== undefined && !TONES.includes(tone)) {
      res.status(400).json({ error: `tone invalido. Valores aceitos: ${TONES.join(", ")}` });
      return;
    }
    if (formality !== undefined && !FORMALITIES.includes(formality)) {
      res.status(400).json({ error: `formality invalido. Valores aceitos: ${FORMALITIES.join(", ")}` });
      return;
    }
    if (emojiUsage !== undefined && !EMOJI_LEVELS.includes(emojiUsage)) {
      res.status(400).json({ error: `emojiUsage invalido. Valores aceitos: ${EMOJI_LEVELS.join(", ")}` });
      return;
    }
    if (greetingMessage && String(greetingMessage).length > MAX_SHORT_TEXT) {
      res.status(400).json({ error: `greetingMessage muito longo (max ${MAX_SHORT_TEXT} caracteres).` });
      return;
    }
    if (instructions && String(instructions).length > MAX_SHORT_TEXT) {
      res.status(400).json({ error: `instructions muito longo (max ${MAX_SHORT_TEXT} caracteres).` });
      return;
    }

    const agent = await prisma.agent.upsert({
      where: { businessId: business.id },
      update: {
        ...(name !== undefined ? { name: String(name) } : {}),
        ...(tone !== undefined ? { tone } : {}),
        ...(formality !== undefined ? { formality } : {}),
        ...(emojiUsage !== undefined ? { emojiUsage } : {}),
        ...(greetingMessage !== undefined ? { greetingMessage: greetingMessage === null ? null : String(greetingMessage) } : {}),
        ...(instructions !== undefined ? { instructions: instructions === null ? null : String(instructions) } : {}),
        ...(active !== undefined ? { active: Boolean(active) } : {}),
      },
      create: {
        businessId: business.id,
        ...(name !== undefined ? { name: String(name) } : {}),
        ...(tone !== undefined ? { tone } : {}),
        ...(formality !== undefined ? { formality } : {}),
        ...(emojiUsage !== undefined ? { emojiUsage } : {}),
        ...(greetingMessage ? { greetingMessage: String(greetingMessage) } : {}),
        ...(instructions ? { instructions: String(instructions) } : {}),
        ...(active !== undefined ? { active: Boolean(active) } : {}),
      },
    });
    res.json(agent);
  })
);

// --- Base de conhecimento ---

agentRouter.get(
  "/knowledge",
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const categoryParam = req.query.category;
    const category =
      typeof categoryParam === "string" && KNOWLEDGE_CATEGORIES.includes(categoryParam as KnowledgeCategory)
        ? (categoryParam as KnowledgeCategory)
        : undefined;

    const entries = await prisma.knowledgeEntry.findMany({
      where: { businessId: business.id, ...(category ? { category } : {}) },
      orderBy: { createdAt: "desc" },
    });
    res.json(entries);
  })
);

agentRouter.post(
  "/knowledge",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { category, title, content, language } = req.body ?? {};

    if (!category || !KNOWLEDGE_CATEGORIES.includes(category)) {
      res.status(400).json({ error: `category obrigatorio. Valores aceitos: ${KNOWLEDGE_CATEGORIES.join(", ")}` });
      return;
    }
    if (!title || String(title).length > MAX_TITLE_LENGTH) {
      res.status(400).json({ error: `title obrigatorio (max ${MAX_TITLE_LENGTH} caracteres).` });
      return;
    }
    if (!content || String(content).length > MAX_CONTENT_LENGTH) {
      res.status(400).json({ error: `content obrigatorio (max ${MAX_CONTENT_LENGTH} caracteres).` });
      return;
    }

    const entry = await prisma.knowledgeEntry.create({
      data: {
        businessId: business.id,
        category,
        title: String(title),
        content: String(content),
        language: (language as string) || "pt",
      },
    });
    res.status(201).json(entry);
  })
);

agentRouter.patch(
  "/knowledge/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.knowledgeEntry.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }

    const { category, title, content, language } = req.body ?? {};
    if (category !== undefined && !KNOWLEDGE_CATEGORIES.includes(category)) {
      res.status(400).json({ error: `category invalido. Valores aceitos: ${KNOWLEDGE_CATEGORIES.join(", ")}` });
      return;
    }

    const updated = await prisma.knowledgeEntry.update({
      where: { id: existing.id },
      data: {
        ...(category !== undefined ? { category } : {}),
        ...(title !== undefined ? { title: String(title) } : {}),
        ...(content !== undefined ? { content: String(content) } : {}),
        ...(language !== undefined ? { language: String(language) } : {}),
      },
    });
    res.json(updated);
  })
);

agentRouter.delete(
  "/knowledge/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.knowledgeEntry.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    await prisma.knowledgeEntry.delete({ where: { id: existing.id } });
    res.sendStatus(204);
  })
);

// --- Regras de negocio ---

agentRouter.get(
  "/rules",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const rules = await prisma.businessRule.findMany({
      where: { businessId: business.id },
      orderBy: { createdAt: "asc" },
    });
    res.json(rules);
  })
);

agentRouter.post(
  "/rules",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { description, active } = req.body ?? {};
    if (!description || String(description).length > MAX_SHORT_TEXT) {
      res.status(400).json({ error: `description obrigatoria (max ${MAX_SHORT_TEXT} caracteres).` });
      return;
    }
    const rule = await prisma.businessRule.create({
      data: { businessId: business.id, description: String(description), active: active ?? true },
    });
    res.status(201).json(rule);
  })
);

agentRouter.patch(
  "/rules/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.businessRule.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    const { description, active } = req.body ?? {};
    const updated = await prisma.businessRule.update({
      where: { id: existing.id },
      data: {
        ...(description !== undefined ? { description: String(description) } : {}),
        ...(active !== undefined ? { active: Boolean(active) } : {}),
      },
    });
    res.json(updated);
  })
);

agentRouter.delete(
  "/rules/:id",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const existing = await prisma.businessRule.findFirst({ where: { id: req.params.id, businessId: business.id } });
    if (!existing) {
      res.sendStatus(404);
      return;
    }
    await prisma.businessRule.delete({ where: { id: existing.id } });
    res.sendStatus(204);
  })
);
