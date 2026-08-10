import { Router } from "express";
import { asyncHandler } from "../asyncHandler";
import { currentBusiness, requireMembership, requireRole } from "../auth/middleware";
import { prisma } from "../db";
import { getIndustryTemplate } from "../templates/registry";

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
