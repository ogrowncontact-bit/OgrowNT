
-- AlterTable
ALTER TABLE "catalog"."AssessmentVersion" ADD COLUMN     "shareTemplate" JSONB,
ADD COLUMN     "tensionPairs" JSONB;

-- AlterTable
ALTER TABLE "catalog"."Profile" ADD COLUMN     "priority" INTEGER NOT NULL DEFAULT 0;

