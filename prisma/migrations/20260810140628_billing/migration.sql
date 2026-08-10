-- CreateEnum
CREATE TYPE "SubscriptionStatus" AS ENUM ('TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELED');

-- CreateTable
CREATE TABLE "Plan" (
    "id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "priceMonthly" DECIMAL(10,2) NOT NULL,
    "setupFee" DECIMAL(10,2) NOT NULL DEFAULT 0,
    "currency" TEXT NOT NULL DEFAULT 'BRL',
    "limits" JSONB NOT NULL DEFAULT '{}',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Plan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Subscription" (
    "id" TEXT NOT NULL,
    "businessId" TEXT NOT NULL,
    "planId" TEXT NOT NULL,
    "status" "SubscriptionStatus" NOT NULL DEFAULT 'TRIALING',
    "setupFeePaid" BOOLEAN NOT NULL DEFAULT false,
    "trialEndsAt" TIMESTAMP(3) NOT NULL,
    "currentPeriodEnd" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Subscription_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Plan_key_key" ON "Plan"("key");

-- CreateIndex
CREATE UNIQUE INDEX "Subscription_businessId_key" ON "Subscription"("businessId");

-- AddForeignKey
ALTER TABLE "Subscription" ADD CONSTRAINT "Subscription_businessId_fkey" FOREIGN KEY ("businessId") REFERENCES "Business"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Subscription" ADD CONSTRAINT "Subscription_planId_fkey" FOREIGN KEY ("planId") REFERENCES "Plan"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Planos padrao (Fase 10) - preco vive no banco, nao no codigo (mudar um
-- preco e um UPDATE, nao um deploy). Numeros de lancamento, ajustaveis
-- direto na tabela.
INSERT INTO "Plan" ("id", "key", "name", "priceMonthly", "setupFee", "currency", "limits", "active", "createdAt")
VALUES
  (gen_random_uuid()::text, 'starter', 'Starter', 97.00, 197.00, 'BRL', '{"maxBookingsPerMonth": 200}'::jsonb, true, CURRENT_TIMESTAMP),
  (gen_random_uuid()::text, 'pro', 'Pro', 197.00, 197.00, 'BRL', '{"maxBookingsPerMonth": 1000}'::jsonb, true, CURRENT_TIMESTAMP);

-- Backfill: empresas ja existentes ganham uma Subscription em trial (30
-- dias) no plano Starter, preservando o "primeiro mes gratis" para quem se
-- cadastrou antes desta fase existir.
INSERT INTO "Subscription" ("id", "businessId", "planId", "status", "setupFeePaid", "trialEndsAt", "createdAt", "updatedAt")
SELECT gen_random_uuid()::text, b."id", (SELECT "id" FROM "Plan" WHERE "key" = 'starter'), 'TRIALING'::"SubscriptionStatus", false, CURRENT_TIMESTAMP + INTERVAL '30 days', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM "Business" b;
