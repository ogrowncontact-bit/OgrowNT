/*
  Warnings:

  - Added the required column `passwordHash` to the `AdminUser` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "admin"."AdminUser" ADD COLUMN     "passwordHash" TEXT NOT NULL;
