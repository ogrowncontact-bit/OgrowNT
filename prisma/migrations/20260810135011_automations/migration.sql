/*
  Warnings:

  - You are about to drop the `ReminderLog` table. If the table is not empty, all the data it contains will be lost.

*/
-- CreateEnum
CREATE TYPE "AutomationTrigger" AS ENUM ('BOOKING_REMINDER', 'BOOKING_FOLLOWUP');

-- DropForeignKey
ALTER TABLE "ReminderLog" DROP CONSTRAINT "ReminderLog_bookingId_fkey";

-- DropTable
DROP TABLE "ReminderLog";

-- CreateTable
CREATE TABLE "Automation" (
    "id" TEXT NOT NULL,
    "businessId" TEXT NOT NULL,
    "trigger" "AutomationTrigger" NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "offsetMinutes" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Automation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AutomationLog" (
    "id" TEXT NOT NULL,
    "automationId" TEXT NOT NULL,
    "bookingId" TEXT NOT NULL,
    "sentAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AutomationLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Automation_businessId_idx" ON "Automation"("businessId");

-- CreateIndex
CREATE UNIQUE INDEX "Automation_businessId_trigger_offsetMinutes_key" ON "Automation"("businessId", "trigger", "offsetMinutes");

-- CreateIndex
CREATE UNIQUE INDEX "AutomationLog_automationId_bookingId_key" ON "AutomationLog"("automationId", "bookingId");

-- AddForeignKey
ALTER TABLE "Automation" ADD CONSTRAINT "Automation_businessId_fkey" FOREIGN KEY ("businessId") REFERENCES "Business"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AutomationLog" ADD CONSTRAINT "AutomationLog_automationId_fkey" FOREIGN KEY ("automationId") REFERENCES "Automation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AutomationLog" ADD CONSTRAINT "AutomationLog_bookingId_fkey" FOREIGN KEY ("bookingId") REFERENCES "Booking"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Backfill: preserva o comportamento anterior (lembrete hardcoded 24h e 2h
-- antes, ver config.reminders.offsetsMinutes) para empresas ja existentes,
-- agora como Automation ativas e editaveis por empresa.
INSERT INTO "Automation" ("id", "businessId", "trigger", "active", "offsetMinutes", "createdAt", "updatedAt")
SELECT gen_random_uuid()::text, "id", 'BOOKING_REMINDER'::"AutomationTrigger", true, 1440, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM "Business"
UNION ALL
SELECT gen_random_uuid()::text, "id", 'BOOKING_REMINDER'::"AutomationTrigger", true, 120, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM "Business";
