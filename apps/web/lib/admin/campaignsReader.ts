import { prisma } from "@inner/db";

export interface CampaignRow {
  id: string;
  name: string;
  source: string;
  medium: string;
  campaignParam: string;
  landingSlug: string | null;
  assessmentName: string | null;
  status: string;
  budgetNotes: string | null;
  creativeName: string | null;
  sessions: number;
  paidOrders: number;
}

/** Performance is always computed live from real UTM-tagged sessions/orders — never stored on the Campaign row itself, so it can't drift stale. */
export async function listCampaignsForAdmin(): Promise<CampaignRow[]> {
  const campaigns = await prisma.campaign.findMany({
    orderBy: { updatedAt: "desc" },
    include: { assessment: { select: { name: true } } },
  });

  const rows = await Promise.all(
    campaigns.map(async (c) => {
      const sessions = await prisma.anonymousSession.count({
        where: { utmSource: c.source, utmCampaign: c.campaignParam },
      });
      const paidOrders = await prisma.order.count({
        where: {
          status: "paid",
          assessmentSession: { anonymousSession: { utmSource: c.source, utmCampaign: c.campaignParam } },
        },
      });
      return {
        id: c.id,
        name: c.name,
        source: c.source,
        medium: c.medium,
        campaignParam: c.campaignParam,
        landingSlug: c.landingSlug,
        assessmentName: c.assessment?.name ?? null,
        status: c.status,
        budgetNotes: c.budgetNotes,
        creativeName: c.creativeName,
        sessions,
        paidOrders,
      };
    })
  );
  return rows;
}

export async function getCampaignById(id: string) {
  return prisma.campaign.findUnique({ where: { id } });
}
