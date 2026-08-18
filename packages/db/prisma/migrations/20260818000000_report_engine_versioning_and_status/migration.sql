
-- CreateEnum
CREATE TYPE "commerce"."ReportStatus" AS ENUM ('pending', 'generating', 'ready', 'failed');

-- AlterTable
ALTER TABLE "commerce"."Order" ADD COLUMN     "language" TEXT NOT NULL DEFAULT 'en';

-- AlterTable
ALTER TABLE "commerce"."Report" ADD COLUMN     "failureReason" TEXT,
ADD COLUMN     "language" TEXT NOT NULL DEFAULT 'en',
ADD COLUMN     "modelVersion" TEXT,
ADD COLUMN     "promptVersion" INTEGER,
ADD COLUMN     "reportEngineVersion" INTEGER,
ADD COLUMN     "status" "commerce"."ReportStatus" NOT NULL DEFAULT 'ready',
ALTER COLUMN "content" DROP NOT NULL;

-- CreateIndex
CREATE UNIQUE INDEX "Report_orderId_key" ON "commerce"."Report"("orderId");

