-- CreateTable
CREATE TABLE "catalog"."QaSimulationRun" (
    "id" TEXT NOT NULL,
    "assessmentSlug" TEXT NOT NULL,
    "personaCount" INTEGER NOT NULL,
    "resultJson" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "QaSimulationRun_pkey" PRIMARY KEY ("id")
);
