-- AlterTable
ALTER TABLE "Business" ADD COLUMN     "address" TEXT,
ADD COLUMN     "description" TEXT,
ADD COLUMN     "metadata" JSONB NOT NULL DEFAULT '{}',
ADD COLUMN     "phone" TEXT;

-- AlterTable
ALTER TABLE "Service" ADD COLUMN     "metadata" JSONB NOT NULL DEFAULT '{}';
