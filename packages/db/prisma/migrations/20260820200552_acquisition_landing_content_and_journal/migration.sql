-- CreateEnum
CREATE TYPE "catalog"."JournalPostStatus" AS ENUM ('draft', 'published', 'archived');

-- AlterTable
ALTER TABLE "catalog"."Assessment" ADD COLUMN     "ctaLabel" TEXT,
ADD COLUMN     "curiosityHook" TEXT,
ADD COLUMN     "exampleInsight" TEXT,
ADD COLUMN     "extraFaqItems" JSONB,
ADD COLUMN     "landingHeadline" TEXT,
ADD COLUMN     "landingSubheadline" TEXT;

-- CreateTable
CREATE TABLE "catalog"."JournalPost" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "excerpt" TEXT NOT NULL,
    "body" TEXT NOT NULL,
    "status" "catalog"."JournalPostStatus" NOT NULL DEFAULT 'draft',
    "publishedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "JournalPost_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "JournalPost_slug_key" ON "catalog"."JournalPost"("slug");
