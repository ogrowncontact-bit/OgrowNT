-- AlterTable
CREATE UNIQUE INDEX "Unsubscribe_userId_scope_key" ON "marketing"."Unsubscribe"("userId", "scope");
