-- CreateEnum
CREATE TYPE "ChannelType" AS ENUM ('WHATSAPP', 'INSTAGRAM');

-- AlterTable
ALTER TABLE "Conversation" ADD COLUMN     "channel" "ChannelType" NOT NULL DEFAULT 'WHATSAPP';
