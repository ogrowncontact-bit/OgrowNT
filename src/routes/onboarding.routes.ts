import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { config } from "../config";
import { encryptSecret } from "../crypto";
import { prisma } from "../db";
import { getIndustryTemplate } from "../templates/registry";
import { extractServicesFromText, fetchWebsiteText } from "../onboarding/websiteImport";

// Rotas de "Business Setup": expoe o template do nicho da empresa (campos
// sugeridos, servicos de exemplo) e um checklist de onboarding, alem de um
// atalho para popular servicos/horarios padrao (quick-start). Autocontido
// (roda sua propria requireMembership) para nao depender da ordem de
// montagem em relacao a outros routers em /api/businesses/:businessId.
export const onboardingRouter = Router({ mergeParams: true });

const WRITE_ROLES = ["OWNER", "ADMIN"] as const;

onboardingRouter.use(requireMembership);

onboardingRouter.get(
  "/onboarding",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const template = getIndustryTemplate(business.industry);

    const [serviceCount, hoursCount, whatsAppAccount] = await Promise.all([
      prisma.service.count({ where: { businessId: business.id } }),
      prisma.businessHours.count({ where: { businessId: business.id } }),
      prisma.whatsAppAccount.findUnique({ where: { businessId: business.id } }),
    ]);

    res.json({
      template,
      checklist: {
        profileComplete: Boolean(business.description && business.address && business.phone),
        hasServices: serviceCount > 0,
        hasBusinessHours: hoursCount > 0,
        hasWhatsAppConnected: whatsAppAccount !== null,
      },
    });
  })
);

// Popula servicos de exemplo e um horario de funcionamento padrao a partir do
// template do nicho - so cria o que ainda nao existe (idempotente, seguro de
// chamar mais de uma vez). O dono edita/ajusta depois via PATCH /services e
// PUT /business-hours.
onboardingRouter.post(
  "/onboarding/quick-start",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const template = getIndustryTemplate(business.industry);

    const [existingServiceCount, existingHoursCount] = await Promise.all([
      prisma.service.count({ where: { businessId: business.id } }),
      prisma.businessHours.count({ where: { businessId: business.id } }),
    ]);

    let createdServices = 0;
    if (existingServiceCount === 0 && template.defaultServices.length > 0) {
      await prisma.service.createMany({
        data: template.defaultServices.map((s) => ({
          businessId: business.id,
          name: s.name,
          durationMinutes: s.durationMinutes,
        })),
      });
      createdServices = template.defaultServices.length;
    }

    let createdHours = false;
    if (existingHoursCount === 0) {
      await prisma.businessHours.createMany({
        data: [1, 2, 3, 4, 5, 6].map((weekday) => ({
          businessId: business.id,
          weekday,
          openTime: "09:00",
          closeTime: "18:00",
        })),
      });
      createdHours = true;
    }

    res.json({
      createdServices,
      createdHours,
      message:
        createdServices === 0 && !createdHours
          ? "Ja havia servicos e horarios configurados - nada foi alterado."
          : "Configuracao inicial criada. Ajuste precos, duracoes e horarios quando quiser.",
    });
  })
);

// Le o site da empresa e usa a IA (mesma conta/chave usada pelo agente de
// conversas - ver src/ai/agent.ts) para sugerir servicos/precos a importar.
// Nao grava nada no banco: so devolve sugestoes, o dono confirma quais
// quer criar (via POST /services, ja existente) depois de revisar.
onboardingRouter.post(
  "/onboarding/import-from-website",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    if (!config.anthropic.apiKey) {
      res.status(501).json({
        error:
          "Importacao automatica requer a IA configurada (ANTHROPIC_API_KEY) no backend. Cadastre os servicos manualmente por enquanto.",
      });
      return;
    }

    const business = currentBusiness(res);
    const { url } = req.body ?? {};
    if (!url || typeof url !== "string") {
      res.status(400).json({ error: "url e obrigatoria." });
      return;
    }

    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      res.status(400).json({ error: "URL invalida." });
      return;
    }

    let pageText: string;
    try {
      pageText = await fetchWebsiteText(parsedUrl.toString());
    } catch (err) {
      res.status(422).json({ error: err instanceof Error ? err.message : "Nao foi possivel acessar essa URL." });
      return;
    }

    if (!pageText || pageText.length < 30) {
      res.status(422).json({ error: "Nao encontramos texto suficiente nessa pagina para analisar." });
      return;
    }

    const template = getIndustryTemplate(business.industry);
    let suggestions;
    try {
      suggestions = await extractServicesFromText(pageText, template.label);
    } catch (err) {
      res.status(502).json({ error: err instanceof Error ? err.message : "Nao foi possivel interpretar os servicos dessa pagina." });
      return;
    }

    if (suggestions.length === 0) {
      res.status(422).json({ error: "Nao encontramos servicos ou precos reconheciveis nessa pagina." });
      return;
    }

    res.json({ sourceUrl: parsedUrl.toString(), suggestions });
  })
);

function whatsAppAccountView(account: {
  phoneNumberId: string;
  wabaId: string;
  verifiedName: string | null;
  connectedAt: Date;
}) {
  return {
    connected: true,
    phoneNumberId: account.phoneNumberId,
    wabaId: account.wabaId,
    verifiedName: account.verifiedName,
    connectedAt: account.connectedAt,
  };
}

// Le o numero de WhatsApp conectado (sem expor o access token, que fica
// criptografado no banco - ver src/crypto.ts).
onboardingRouter.get(
  "/whatsapp",
  asyncHandler(async (_req, res) => {
    const business = currentBusiness(res);
    const account = await prisma.whatsAppAccount.findUnique({ where: { businessId: business.id } });
    res.json(account ? whatsAppAccountView(account) : { connected: false });
  })
);

// Conecta (ou atualiza) o numero de WhatsApp Business Cloud API da empresa.
// phoneNumberId, wabaId e accessToken vem do Meta Business Manager - ver
// guia de deploy. O token e criptografado antes de ir pro banco.
onboardingRouter.put(
  "/whatsapp",
  requireRole(...WRITE_ROLES),
  asyncHandler(async (req, res) => {
    const business = currentBusiness(res);
    const { phoneNumberId, wabaId, accessToken, verifiedName } = req.body ?? {};

    if (!phoneNumberId || !wabaId || !accessToken) {
      res.status(400).json({ error: "phoneNumberId, wabaId e accessToken sao obrigatorios." });
      return;
    }

    const data = {
      phoneNumberId: String(phoneNumberId),
      wabaId: String(wabaId),
      verifiedName: verifiedName ? String(verifiedName) : null,
      encryptedAccessToken: encryptSecret(String(accessToken)),
    };

    try {
      const account = await prisma.whatsAppAccount.upsert({
        where: { businessId: business.id },
        update: data,
        create: { businessId: business.id, ...data },
      });
      res.json(whatsAppAccountView(account));
    } catch (err) {
      if ((err as { code?: string }).code === "P2002") {
        res.status(409).json({ error: "Esse numero de WhatsApp ja esta conectado a outra empresa." });
        return;
      }
      throw err;
    }
  })
);
