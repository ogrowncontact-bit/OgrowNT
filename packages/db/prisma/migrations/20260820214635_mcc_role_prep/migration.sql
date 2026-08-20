-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "admin"."AdminRole" ADD VALUE 'founder';
ALTER TYPE "admin"."AdminRole" ADD VALUE 'admin';
ALTER TYPE "admin"."AdminRole" ADD VALUE 'content_editor';
ALTER TYPE "admin"."AdminRole" ADD VALUE 'support';
ALTER TYPE "admin"."AdminRole" ADD VALUE 'analyst';
