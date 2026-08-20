-- CreateEnum
CREATE TYPE "admin"."PromptTemplateStatus" AS ENUM ('draft', 'testing', 'published', 'archived');

-- AlterTable
ALTER TABLE "commerce"."Report" ADD COLUMN     "assessmentVersion" INTEGER NOT NULL DEFAULT 1,
ADD COLUMN     "personaVersion" INTEGER;

-- CreateTable
CREATE TABLE "admin"."PromptTemplate" (
    "id" TEXT NOT NULL,
    "assessmentSlug" TEXT NOT NULL,
    "version" INTEGER NOT NULL,
    "status" "admin"."PromptTemplateStatus" NOT NULL DEFAULT 'draft',
    "personaName" TEXT NOT NULL,
    "personaFocus" TEXT NOT NULL,
    "personaPrompt" TEXT NOT NULL,
    "toneWarmth" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "toneDirectness" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "toneDepth" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "toneFormality" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "createdByAdminId" TEXT,
    "publishedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "PromptTemplate_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "PromptTemplate_assessmentSlug_status_idx" ON "admin"."PromptTemplate"("assessmentSlug", "status");

-- CreateIndex
CREATE UNIQUE INDEX "PromptTemplate_assessmentSlug_version_key" ON "admin"."PromptTemplate"("assessmentSlug", "version");
