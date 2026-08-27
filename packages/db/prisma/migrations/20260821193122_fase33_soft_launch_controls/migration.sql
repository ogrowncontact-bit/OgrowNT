-- CreateEnum
CREATE TYPE "runtime"."AbandonmentFeedbackReason" AS ENUM ('too_expensive', 'not_sure_useful', 'wanted_to_think', 'not_enough_info', 'technical_problem', 'other');

-- CreateEnum
CREATE TYPE "commerce"."PurchaseFeedbackReason" AS ENUM ('curiosity', 'free_result_accurate', 'wanted_more_detail', 'preview_convinced', 'price_reasonable', 'other');

-- CreateEnum
CREATE TYPE "admin"."SupportTicketCategory" AS ENUM ('payment', 'report', 'email', 'technical', 'content');

-- CreateEnum
CREATE TYPE "admin"."SupportTicketStatus" AS ENUM ('open', 'resolved');

-- AlterTable
ALTER TABLE "catalog"."Assessment" ADD COLUMN     "releaseVersion" TEXT NOT NULL DEFAULT '1.0';

-- AlterTable
ALTER TABLE "catalog"."Question" ADD COLUMN     "disabledAt" TIMESTAMP(3);

-- AlterTable
ALTER TABLE "commerce"."Report" ADD COLUMN     "assessmentReleaseVersion" TEXT;

-- AlterTable
ALTER TABLE "identity"."AnonymousSession" ADD COLUMN     "deviceType" TEXT;

-- CreateTable
CREATE TABLE "runtime"."AbandonmentFeedback" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "reason" "runtime"."AbandonmentFeedbackReason" NOT NULL,
    "otherText" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AbandonmentFeedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "commerce"."PurchaseFeedback" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "reason" "commerce"."PurchaseFeedbackReason" NOT NULL,
    "otherText" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PurchaseFeedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admin"."SupportTicket" (
    "id" TEXT NOT NULL,
    "category" "admin"."SupportTicketCategory" NOT NULL,
    "email" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "status" "admin"."SupportTicketStatus" NOT NULL DEFAULT 'open',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SupportTicket_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admin"."FeatureFlags" (
    "id" TEXT NOT NULL DEFAULT 'singleton',
    "purchasesPaused" BOOLEAN NOT NULL DEFAULT false,
    "reportGenerationPaused" BOOLEAN NOT NULL DEFAULT false,
    "aiForceFallback" BOOLEAN NOT NULL DEFAULT false,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "updatedByAdminId" TEXT,

    CONSTRAINT "FeatureFlags_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "AbandonmentFeedback_assessmentSessionId_key" ON "runtime"."AbandonmentFeedback"("assessmentSessionId");

-- CreateIndex
CREATE UNIQUE INDEX "PurchaseFeedback_orderId_key" ON "commerce"."PurchaseFeedback"("orderId");

-- AddForeignKey
ALTER TABLE "runtime"."AbandonmentFeedback" ADD CONSTRAINT "AbandonmentFeedback_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."PurchaseFeedback" ADD CONSTRAINT "PurchaseFeedback_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "commerce"."Order"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
