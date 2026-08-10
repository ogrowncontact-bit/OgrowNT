-- AlterTable
ALTER TABLE "Business" ADD COLUMN     "currency" TEXT NOT NULL DEFAULT 'BRL',
ADD COLUMN     "defaultLanguage" TEXT NOT NULL DEFAULT 'pt',
ADD COLUMN     "supportedLanguages" TEXT[] DEFAULT ARRAY['pt']::TEXT[];

-- AlterTable
ALTER TABLE "Conversation" ADD COLUMN     "detectedLanguage" TEXT;

-- AlterTable
ALTER TABLE "Customer" ADD COLUMN     "preferredLanguage" TEXT NOT NULL DEFAULT 'auto';
