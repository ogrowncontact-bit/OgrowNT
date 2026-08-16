/*
  Warnings:

  - Added the required column `bridgeCopy` to the `RecommendationRule` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "catalog"."AssessmentVersion" ADD COLUMN     "freeResultTemplate" JSONB;

-- AlterTable
ALTER TABLE "catalog"."RecommendationRule" ADD COLUMN     "bridgeCopy" TEXT NOT NULL;
