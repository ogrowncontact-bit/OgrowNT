import { prisma } from "@inner/db";

/**
 * DB-backed sliding-window request counter — no Redis/external cache in
 * this stack, and the volumes this guards (magic-link requests) are low
 * enough that a table scan per check is fine. Records every attempt
 * (allowed or not) so a sustained burst is still visible after the fact,
 * and lazily prunes rows outside the window for the same scope+identifier
 * so the table doesn't grow unbounded.
 */
export async function checkRateLimit(
  scope: string,
  identifier: string,
  opts: { maxAttempts: number; windowMs: number }
): Promise<{ allowed: boolean }> {
  const windowStart = new Date(Date.now() - opts.windowMs);

  const [, recentCount] = await Promise.all([
    prisma.rateLimitHit.deleteMany({ where: { scope, identifier, createdAt: { lt: windowStart } } }),
    prisma.rateLimitHit.count({ where: { scope, identifier, createdAt: { gte: windowStart } } }),
  ]);

  if (recentCount >= opts.maxAttempts) return { allowed: false };

  await prisma.rateLimitHit.create({ data: { scope, identifier } });
  return { allowed: true };
}
