-- AlterTable
ALTER TABLE "identity"."User" ADD COLUMN     "lastSeenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- AlterTable
ALTER TABLE "marketing"."EmailEvent" ADD COLUMN     "attempts" INTEGER NOT NULL DEFAULT 1,
ADD COLUMN     "bouncedAt" TIMESTAMP(3),
ADD COLUMN     "deliveredAt" TIMESTAMP(3),
ADD COLUMN     "failureReason" TEXT,
ADD COLUMN     "providerRef" TEXT,
ADD COLUMN     "status" TEXT NOT NULL DEFAULT 'sent',
ADD COLUMN     "transactional" BOOLEAN NOT NULL DEFAULT true;

-- CreateTable
CREATE TABLE "identity"."UsedAccessToken" (
    "tokenHash" TEXT NOT NULL,
    "usedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "UsedAccessToken_pkey" PRIMARY KEY ("tokenHash")
);

-- CreateTable
CREATE TABLE "identity"."RateLimitHit" (
    "id" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "identifier" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RateLimitHit_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "RateLimitHit_scope_identifier_createdAt_idx" ON "identity"."RateLimitHit"("scope", "identifier", "createdAt");

-- CreateIndex
CREATE INDEX "EmailEvent_providerRef_idx" ON "marketing"."EmailEvent"("providerRef");
