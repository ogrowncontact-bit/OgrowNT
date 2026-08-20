import { prisma } from "@inner/db";

export interface CampaignInput {
  name: string;
  source: string;
  medium: string;
  campaignParam: string;
  landingSlug?: string | null;
  assessmentId?: string | null;
  budgetNotes?: string | null;
  creativeName?: string | null;
}

export async function createCampaign(input: CampaignInput): Promise<{ id: string }> {
  const row = await prisma.campaign.create({
    data: {
      name: input.name,
      source: input.source,
      medium: input.medium,
      campaignParam: input.campaignParam,
      landingSlug: input.landingSlug || null,
      assessmentId: input.assessmentId || null,
      budgetNotes: input.budgetNotes || null,
      creativeName: input.creativeName || null,
    },
  });
  return { id: row.id };
}

export async function updateCampaign(id: string, input: Partial<CampaignInput>): Promise<void> {
  await prisma.campaign.update({
    where: { id },
    data: {
      name: input.name,
      source: input.source,
      medium: input.medium,
      campaignParam: input.campaignParam,
      landingSlug: input.landingSlug || null,
      assessmentId: input.assessmentId || null,
      budgetNotes: input.budgetNotes || null,
      creativeName: input.creativeName || null,
    },
  });
}

export async function setCampaignStatus(id: string, status: "draft" | "active" | "paused" | "ended"): Promise<void> {
  await prisma.campaign.update({ where: { id }, data: { status } });
}
