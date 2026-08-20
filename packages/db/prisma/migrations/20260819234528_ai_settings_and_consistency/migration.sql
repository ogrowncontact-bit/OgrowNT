-- AlterTable
ALTER TABLE "runtime"."DimensionScore" ADD COLUMN     "consistency" DOUBLE PRECISION;

-- CreateTable
CREATE TABLE "admin"."AiSettings" (
    "id" TEXT NOT NULL DEFAULT 'singleton',
    "fastModel" TEXT NOT NULL,
    "qualityModel" TEXT NOT NULL,
    "temperature" DOUBLE PRECISION NOT NULL,
    "maxTokens" INTEGER NOT NULL,
    "timeoutMs" INTEGER NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "updatedByAdminId" TEXT,

    CONSTRAINT "AiSettings_pkey" PRIMARY KEY ("id")
);
