-- CreateTable
CREATE TABLE "admin"."AiCallLog" (
    "id" TEXT NOT NULL,
    "module" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "occurredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "latencyMs" INTEGER NOT NULL,
    "inputTokens" INTEGER,
    "outputTokens" INTEGER,
    "ok" BOOLEAN NOT NULL,
    "errorReason" TEXT,

    CONSTRAINT "AiCallLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AiCallLog_module_occurredAt_idx" ON "admin"."AiCallLog"("module", "occurredAt");

