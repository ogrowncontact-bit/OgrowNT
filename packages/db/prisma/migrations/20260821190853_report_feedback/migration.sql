-- CreateEnum
CREATE TYPE "commerce"."FeedbackRating" AS ENUM ('very_accurate', 'mostly_accurate', 'somewhat_accurate', 'not_very_accurate', 'not_accurate');

-- CreateTable
CREATE TABLE "commerce"."ReportFeedback" (
    "id" TEXT NOT NULL,
    "reportId" TEXT NOT NULL,
    "rating" "commerce"."FeedbackRating" NOT NULL,
    "comment" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ReportFeedback_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ReportFeedback_reportId_key" ON "commerce"."ReportFeedback"("reportId");

-- AddForeignKey
ALTER TABLE "commerce"."ReportFeedback" ADD CONSTRAINT "ReportFeedback_reportId_fkey" FOREIGN KEY ("reportId") REFERENCES "commerce"."Report"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
