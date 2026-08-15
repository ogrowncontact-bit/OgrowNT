-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "admin";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "analytics";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "catalog";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "commerce";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "identity";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "marketing";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "runtime";

-- CreateEnum
CREATE TYPE "identity"."DeletionStatus" AS ENUM ('requested', 'completed');

-- CreateEnum
CREATE TYPE "catalog"."AssessmentStatus" AS ENUM ('draft', 'published', 'archived');

-- CreateEnum
CREATE TYPE "catalog"."QuestionType" AS ENUM ('single_select', 'multi_select', 'scale', 'open_text');

-- CreateEnum
CREATE TYPE "catalog"."ProductType" AS ENUM ('individual', 'deep', 'bundle', 'couple', 'master');

-- CreateEnum
CREATE TYPE "runtime"."SessionStatus" AS ENUM ('in_progress', 'completed', 'abandoned');

-- CreateEnum
CREATE TYPE "commerce"."OrderStatus" AS ENUM ('pending', 'paid', 'refunded', 'failed');

-- CreateEnum
CREATE TYPE "marketing"."UnsubscribeScope" AS ENUM ('all', 'recommendations');

-- CreateEnum
CREATE TYPE "admin"."AdminRole" AS ENUM ('owner', 'editor', 'viewer');

-- CreateTable
CREATE TABLE "identity"."AnonymousSession" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastSeenAt" TIMESTAMP(3) NOT NULL,
    "firstLandingSlug" TEXT NOT NULL,
    "utmSource" TEXT,
    "utmMedium" TEXT,
    "utmCampaign" TEXT,
    "utmContent" TEXT,
    "utmTerm" TEXT,
    "referrer" TEXT,
    "ipHash" TEXT,
    "uaHash" TEXT,
    "userId" TEXT,

    CONSTRAINT "AnonymousSession_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "identity"."User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "emailVerifiedAt" TIMESTAMP(3),
    "stripeCustomerId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "identity"."DeletionRequest" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status" "identity"."DeletionStatus" NOT NULL DEFAULT 'requested',
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "DeletionRequest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."Assessment" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "hook" TEXT NOT NULL,
    "targetAudience" TEXT NOT NULL,
    "status" "catalog"."AssessmentStatus" NOT NULL DEFAULT 'draft',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Assessment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."AssessmentVersion" (
    "id" TEXT NOT NULL,
    "assessmentId" TEXT NOT NULL,
    "versionNumber" INTEGER NOT NULL,
    "minQuestions" INTEGER NOT NULL,
    "recommendedQuestions" INTEGER NOT NULL,
    "maxQuestions" INTEGER NOT NULL,
    "aiInfluenceCap" DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    "publishedAt" TIMESTAMP(3),
    "createdBy" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AssessmentVersion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."Dimension" (
    "id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "description" TEXT NOT NULL,

    CONSTRAINT "Dimension_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."AssessmentDimension" (
    "id" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "dimensionId" TEXT NOT NULL,
    "weight" DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    CONSTRAINT "AssessmentDimension_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."Question" (
    "id" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "type" "catalog"."QuestionType" NOT NULL,
    "isCore" BOOLEAN NOT NULL DEFAULT true,
    "prompt" TEXT NOT NULL,
    "orderHint" INTEGER NOT NULL,
    "metadata" JSONB,

    CONSTRAINT "Question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."QuestionOption" (
    "id" TEXT NOT NULL,
    "questionId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "dimensionContributions" JSONB NOT NULL,
    "orderHint" INTEGER NOT NULL,

    CONSTRAINT "QuestionOption_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."AdaptiveRule" (
    "id" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "trigger" JSONB NOT NULL,
    "action" JSONB NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "AdaptiveRule_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."Profile" (
    "id" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "descriptionTemplate" TEXT NOT NULL,
    "matchingRule" JSONB NOT NULL,

    CONSTRAINT "Profile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."ReportTemplate" (
    "id" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "sections" JSONB NOT NULL,

    CONSTRAINT "ReportTemplate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."RecommendationRule" (
    "id" TEXT NOT NULL,
    "fromAssessmentId" TEXT NOT NULL,
    "toAssessmentId" TEXT NOT NULL,
    "condition" JSONB NOT NULL,
    "weight" DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    CONSTRAINT "RecommendationRule_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog"."Price" (
    "id" TEXT NOT NULL,
    "assessmentId" TEXT NOT NULL,
    "productType" "catalog"."ProductType" NOT NULL,
    "amountCents" INTEGER NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'EUR',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "effectiveFrom" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Price_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."AssessmentSession" (
    "id" TEXT NOT NULL,
    "anonymousSessionId" TEXT NOT NULL,
    "assessmentId" TEXT NOT NULL,
    "assessmentVersionId" TEXT NOT NULL,
    "status" "runtime"."SessionStatus" NOT NULL DEFAULT 'in_progress',
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "questionCount" INTEGER NOT NULL DEFAULT 0,
    "sourceSlug" TEXT NOT NULL,

    CONSTRAINT "AssessmentSession_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."Response" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "questionId" TEXT NOT NULL,
    "selectedOptionIds" JSONB,
    "scaleValue" INTEGER,
    "answeredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "responseTimeMs" INTEGER,

    CONSTRAINT "Response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."OpenResponse" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "questionId" TEXT NOT NULL,
    "rawTextEncrypted" TEXT NOT NULL,
    "aiTags" JSONB,
    "aiSentiment" TEXT,
    "safetyFlag" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "OpenResponse_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."AiFollowup" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "triggeredByQuestionId" TEXT NOT NULL,
    "generatedText" TEXT NOT NULL,
    "generatedOptions" JSONB,
    "reasonCode" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AiFollowup_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."DimensionScore" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "dimensionKey" TEXT NOT NULL,
    "rawScore" DOUBLE PRECISION NOT NULL,
    "normalizedScore" DOUBLE PRECISION NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,

    CONSTRAINT "DimensionScore_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "runtime"."ProfileResult" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "primaryProfileKey" TEXT NOT NULL,
    "secondaryProfileKeys" JSONB NOT NULL,
    "aiSemanticNotes" JSONB,
    "computedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ProfileResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "commerce"."Order" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "priceId" TEXT NOT NULL,
    "amountCents" INTEGER NOT NULL,
    "currency" TEXT NOT NULL,
    "status" "commerce"."OrderStatus" NOT NULL DEFAULT 'pending',
    "provider" TEXT NOT NULL,
    "providerRef" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "paidAt" TIMESTAMP(3),

    CONSTRAINT "Order_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "commerce"."Entitlement" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "reportId" TEXT,
    "grantedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3),

    CONSTRAINT "Entitlement_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "commerce"."Report" (
    "id" TEXT NOT NULL,
    "assessmentSessionId" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "templateVersion" INTEGER NOT NULL,
    "content" JSONB NOT NULL,
    "pdfObjectKey" TEXT,
    "generatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deliveredAt" TIMESTAMP(3),

    CONSTRAINT "Report_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "commerce"."Refund" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "amountCents" INTEGER NOT NULL,
    "reason" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Refund_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "marketing"."MarketingConsent" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "consent" BOOLEAN NOT NULL,
    "consentTimestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "consentVersion" TEXT NOT NULL,
    "consentSource" TEXT NOT NULL,
    "campaign" TEXT,
    "assessmentId" TEXT,

    CONSTRAINT "MarketingConsent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "marketing"."EmailEvent" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "templateKey" TEXT NOT NULL,
    "sentAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "openedAt" TIMESTAMP(3),
    "clickedAt" TIMESTAMP(3),

    CONSTRAINT "EmailEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "marketing"."Unsubscribe" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "scope" "marketing"."UnsubscribeScope" NOT NULL,
    "unsubscribedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Unsubscribe_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "analytics"."Event" (
    "id" TEXT NOT NULL,
    "occurredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "anonymousSessionId" TEXT NOT NULL,
    "userId" TEXT,
    "eventName" TEXT NOT NULL,
    "assessmentId" TEXT,
    "properties" JSONB,
    "utmSource" TEXT,
    "utmMedium" TEXT,
    "utmCampaign" TEXT,
    "utmContent" TEXT,
    "utmTerm" TEXT,

    CONSTRAINT "Event_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admin"."AdminUser" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "role" "admin"."AdminRole" NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AdminUser_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admin"."AuditLog" (
    "id" TEXT NOT NULL,
    "adminUserId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "diff" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "identity"."User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "Assessment_slug_key" ON "catalog"."Assessment"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "AssessmentVersion_assessmentId_versionNumber_key" ON "catalog"."AssessmentVersion"("assessmentId", "versionNumber");

-- CreateIndex
CREATE UNIQUE INDEX "Dimension_key_key" ON "catalog"."Dimension"("key");

-- CreateIndex
CREATE UNIQUE INDEX "AssessmentDimension_assessmentVersionId_dimensionId_key" ON "catalog"."AssessmentDimension"("assessmentVersionId", "dimensionId");

-- CreateIndex
CREATE UNIQUE INDEX "Question_assessmentVersionId_key_key" ON "catalog"."Question"("assessmentVersionId", "key");

-- CreateIndex
CREATE UNIQUE INDEX "QuestionOption_questionId_key_key" ON "catalog"."QuestionOption"("questionId", "key");

-- CreateIndex
CREATE UNIQUE INDEX "AdaptiveRule_assessmentVersionId_key_key" ON "catalog"."AdaptiveRule"("assessmentVersionId", "key");

-- CreateIndex
CREATE UNIQUE INDEX "Profile_assessmentVersionId_key_key" ON "catalog"."Profile"("assessmentVersionId", "key");

-- CreateIndex
CREATE UNIQUE INDEX "ReportTemplate_assessmentVersionId_key" ON "catalog"."ReportTemplate"("assessmentVersionId");

-- CreateIndex
CREATE UNIQUE INDEX "DimensionScore_assessmentSessionId_dimensionKey_key" ON "runtime"."DimensionScore"("assessmentSessionId", "dimensionKey");

-- CreateIndex
CREATE UNIQUE INDEX "ProfileResult_assessmentSessionId_key" ON "runtime"."ProfileResult"("assessmentSessionId");

-- CreateIndex
CREATE UNIQUE INDEX "Entitlement_orderId_key" ON "commerce"."Entitlement"("orderId");

-- CreateIndex
CREATE UNIQUE INDEX "Entitlement_reportId_key" ON "commerce"."Entitlement"("reportId");

-- CreateIndex
CREATE INDEX "Event_eventName_occurredAt_idx" ON "analytics"."Event"("eventName", "occurredAt");

-- CreateIndex
CREATE INDEX "Event_anonymousSessionId_idx" ON "analytics"."Event"("anonymousSessionId");

-- CreateIndex
CREATE UNIQUE INDEX "AdminUser_email_key" ON "admin"."AdminUser"("email");

-- AddForeignKey
ALTER TABLE "identity"."AnonymousSession" ADD CONSTRAINT "AnonymousSession_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "identity"."DeletionRequest" ADD CONSTRAINT "DeletionRequest_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."AssessmentVersion" ADD CONSTRAINT "AssessmentVersion_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."AssessmentDimension" ADD CONSTRAINT "AssessmentDimension_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."AssessmentDimension" ADD CONSTRAINT "AssessmentDimension_dimensionId_fkey" FOREIGN KEY ("dimensionId") REFERENCES "catalog"."Dimension"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."Question" ADD CONSTRAINT "Question_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."QuestionOption" ADD CONSTRAINT "QuestionOption_questionId_fkey" FOREIGN KEY ("questionId") REFERENCES "catalog"."Question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."AdaptiveRule" ADD CONSTRAINT "AdaptiveRule_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."Profile" ADD CONSTRAINT "Profile_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."ReportTemplate" ADD CONSTRAINT "ReportTemplate_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."RecommendationRule" ADD CONSTRAINT "RecommendationRule_fromAssessmentId_fkey" FOREIGN KEY ("fromAssessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."RecommendationRule" ADD CONSTRAINT "RecommendationRule_toAssessmentId_fkey" FOREIGN KEY ("toAssessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catalog"."Price" ADD CONSTRAINT "Price_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."AssessmentSession" ADD CONSTRAINT "AssessmentSession_anonymousSessionId_fkey" FOREIGN KEY ("anonymousSessionId") REFERENCES "identity"."AnonymousSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."AssessmentSession" ADD CONSTRAINT "AssessmentSession_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "catalog"."Assessment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."AssessmentSession" ADD CONSTRAINT "AssessmentSession_assessmentVersionId_fkey" FOREIGN KEY ("assessmentVersionId") REFERENCES "catalog"."AssessmentVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."Response" ADD CONSTRAINT "Response_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."OpenResponse" ADD CONSTRAINT "OpenResponse_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."AiFollowup" ADD CONSTRAINT "AiFollowup_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."DimensionScore" ADD CONSTRAINT "DimensionScore_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "runtime"."ProfileResult" ADD CONSTRAINT "ProfileResult_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Order" ADD CONSTRAINT "Order_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Order" ADD CONSTRAINT "Order_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Order" ADD CONSTRAINT "Order_priceId_fkey" FOREIGN KEY ("priceId") REFERENCES "catalog"."Price"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Entitlement" ADD CONSTRAINT "Entitlement_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Entitlement" ADD CONSTRAINT "Entitlement_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Entitlement" ADD CONSTRAINT "Entitlement_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "commerce"."Order"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Entitlement" ADD CONSTRAINT "Entitlement_reportId_fkey" FOREIGN KEY ("reportId") REFERENCES "commerce"."Report"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Report" ADD CONSTRAINT "Report_assessmentSessionId_fkey" FOREIGN KEY ("assessmentSessionId") REFERENCES "runtime"."AssessmentSession"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Report" ADD CONSTRAINT "Report_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "commerce"."Order"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "commerce"."Refund" ADD CONSTRAINT "Refund_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "commerce"."Order"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "marketing"."MarketingConsent" ADD CONSTRAINT "MarketingConsent_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "marketing"."EmailEvent" ADD CONSTRAINT "EmailEvent_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "marketing"."Unsubscribe" ADD CONSTRAINT "Unsubscribe_userId_fkey" FOREIGN KEY ("userId") REFERENCES "identity"."User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admin"."AuditLog" ADD CONSTRAINT "AuditLog_adminUserId_fkey" FOREIGN KEY ("adminUserId") REFERENCES "admin"."AdminUser"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
