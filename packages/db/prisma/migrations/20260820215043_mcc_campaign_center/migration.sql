-- CreateEnum
CREATE TYPE "catalog"."CampaignStatus" AS ENUM ('draft', 'active', 'paused', 'ended');

-- CreateTable
CREATE TABLE "catalog"."Campaign" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "medium" TEXT NOT NULL,
    "campaignParam" TEXT NOT NULL,
    "landingSlug" TEXT,
    "assessmentId" TEXT,
    "status" "catalog"."CampaignStatus" NOT NULL DEFAULT 'draft',
    "budgetNotes" TEXT,
    "creativeName" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Campaign_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "catalog"."Campaign" ADD CONSTRAINT "Campaign_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE SET NULL ON UPDATE CASCADE;
