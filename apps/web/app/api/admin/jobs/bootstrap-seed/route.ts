import { randomBytes, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { seedDatabase } from "@inner/db/seed";

function isValidBootstrapSecret(provided: string | null, cronSecret: string | undefined): boolean {
  if (!cronSecret || !provided) return false;
  const expected = Buffer.from(cronSecret);
  const actual = Buffer.from(provided);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

/**
 * One-time production bootstrap: populates a freshly-migrated, empty
 * database with the assessment catalog, dimension pool, recommendation
 * graph, default AI personas, and the seed admin user. GET (not POST)
 * because this is meant to be triggered by opening/fetching a URL once
 * right after a new environment's DATABASE_URL is first configured — same
 * CRON_SECRET already used by the scheduled job routes, passed as a query
 * param since there's no scheduler dispatching this one.
 *
 * Guarded to be a no-op once any Assessment row exists (seedDatabase's
 * assessment-version upsert is not otherwise safe to re-run — see its
 * docstring), so hitting this twice is harmless.
 */
export async function GET(request: NextRequest) {
  const providedSecret = request.nextUrl.searchParams.get("secret");
  if (!isValidBootstrapSecret(providedSecret, process.env.CRON_SECRET)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: process.env.CRON_SECRET ? 401 : 503 });
  }

  const existingCount = await prisma.assessment.count();
  if (existingCount > 0) {
    return NextResponse.json({ skipped: true, reason: "Database already has assessments; refusing to re-run seed.", existingCount });
  }

  // ADMIN_PASSWORD not set in this environment: generate a real one instead
  // of falling back to seedDatabase's dev-only default, since that default
  // is a known value and this environment is reachable from the internet.
  const generatedAdminPassword = process.env.ADMIN_PASSWORD ? undefined : randomBytes(12).toString("base64url");

  const result = await seedDatabase(prisma, generatedAdminPassword ? { adminPassword: generatedAdminPassword } : {});

  return NextResponse.json({
    ok: true,
    adminEmail: result.adminEmail,
    generatedAdminPassword: generatedAdminPassword ?? null,
    note: generatedAdminPassword
      ? "ADMIN_PASSWORD was not set, so this password was generated now and only appears in this response — save it and set ADMIN_EMAIL/ADMIN_PASSWORD in the environment, then rotate it."
      : "Used the ADMIN_PASSWORD already configured in this environment.",
  });
}
