/**
 * FASE 32 §LAUNCH STRATEGY/§SOFT LAUNCH — deploy-time configuration, not
 * runtime-admin-editable state, matching how APP_BASE_URL/CRON_SECRET
 * already work in this codebase. Fully additive and reversible: unset
 * either variable and the product behaves exactly as it always has (full
 * catalog, no cap). Never deletes or unpublishes anything in the DB.
 */

/** Set LAUNCH_MODE_SLUG=love to restrict the public catalog to one experience; every other published assessment still exists and is still reachable by anyone with its direct URL, but Explore/the homepage present it as "Coming Soon" instead of a normal card. */
export function getLaunchModeSlug(): string | null {
  const slug = process.env.LAUNCH_MODE_SLUG?.trim();
  return slug || null;
}

/** Set SOFT_LAUNCH_MAX_USERS to a positive integer to cap how many distinct anonymous visitors can *start* a new assessment — existing/returning visitors are never blocked, only brand-new ones once the cap is reached. */
export function getSoftLaunchMaxUsers(): number | null {
  const raw = Number(process.env.SOFT_LAUNCH_MAX_USERS);
  return Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : null;
}
