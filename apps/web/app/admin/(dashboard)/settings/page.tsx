import { SUPPORTED_REPORT_LANGUAGES, PLANNED_REPORT_LANGUAGES, LANGUAGE_NAMES } from "@inner/ai";
import { getSiteUrl } from "@/lib/siteUrl";
import { getLaunchModeSlug, getSoftLaunchMaxUsers } from "@/lib/launchMode";
import { prisma } from "@inner/db";

export const dynamic = "force-dynamic";

const CURRENCIES = ["EUR", "USD", "GBP", "BRL"];

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={`mr-2 inline-block h-2 w-2 rounded-full ${ok ? "bg-[var(--inner-accent)]" : "bg-[var(--inner-muted)]"}`} />
  );
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const label = "mb-3 text-[13px] font-medium uppercase tracking-[0.1em] text-[var(--inner-muted)]";
const row = "flex items-center justify-between border-b border-[var(--inner-line)] py-2 text-[13px] last:border-0";

export default async function AdminSettingsPage() {
  const stripeConfigured = !!process.env.STRIPE_SECRET_KEY;
  const stripeWebhookConfigured = !!process.env.STRIPE_WEBHOOK_SECRET;
  const resendConfigured = !!process.env.RESEND_API_KEY;
  const anthropicConfigured = !!process.env.ANTHROPIC_API_KEY;
  const cronConfigured = !!process.env.CRON_SECRET;
  const isProduction = process.env.NODE_ENV === "production";

  const launchModeSlug = getLaunchModeSlug();
  const softLaunchMax = getSoftLaunchMaxUsers();
  const currentUserCount = softLaunchMax !== null ? await prisma.anonymousSession.count() : null;

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Settings</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Configuration reference — real status, never a secret value. Nothing on this page can leak an API key.
      </p>

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div className={card}>
          <p className={label}>Brand & domain</p>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Brand</span>
            <span className="text-[var(--inner-ink)]">INNER</span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Domain</span>
            <span className="text-[var(--inner-ink)]">{getSiteUrl()}</span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Environment</span>
            <span className="text-[var(--inner-ink)]">{isProduction ? "Production" : "Development"}</span>
          </div>
        </div>

        <div className={card}>
          <p className={label}>Language</p>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Default</span>
            <span className="text-[var(--inner-ink)]">English</span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Supported (live)</span>
            <span className="text-[var(--inner-ink)]">{SUPPORTED_REPORT_LANGUAGES.map((l) => LANGUAGE_NAMES[l]).join(", ")}</span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Planned (not yet wired)</span>
            <span className="text-[var(--inner-ink)]">{PLANNED_REPORT_LANGUAGES.join(", ").toUpperCase()}</span>
          </div>
        </div>

        <div className={card}>
          <p className={label}>Launch</p>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Catalog</span>
            <span className="text-[var(--inner-ink)]">
              {launchModeSlug ? `LOVE-only launch mode (LAUNCH_MODE_SLUG=${launchModeSlug})` : "Full catalog live"}
            </span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Soft launch cap</span>
            <span className="text-[var(--inner-ink)]">
              {softLaunchMax !== null ? `${currentUserCount} / ${softLaunchMax} visitors` : "Not enabled — open to all traffic"}
            </span>
          </div>
        </div>

        <div className={card}>
          <p className={label}>Currencies</p>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Available at checkout</span>
            <span className="text-[var(--inner-ink)]">{CURRENCIES.join(", ")}</span>
          </div>
        </div>

        <div className={card}>
          <p className={label}>Providers</p>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={stripeConfigured} />
              Payment (Stripe)
            </span>
            <span className="text-[var(--inner-ink)]">{stripeConfigured ? "Configured" : "Not configured (using dev mock)"}</span>
          </div>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={stripeWebhookConfigured} />
              Stripe webhook signing secret
            </span>
            <span className="text-[var(--inner-ink)]">
              {stripeWebhookConfigured
                ? "Configured"
                : isProduction
                  ? "Missing — the app refuses to start in production without this"
                  : "Not configured (using dev mock — no webhook needed)"}
            </span>
          </div>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={resendConfigured} />
              Email (Resend)
            </span>
            <span className="text-[var(--inner-ink)]">{resendConfigured ? "Configured" : "Not configured (using dev local)"}</span>
          </div>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={anthropicConfigured} />
              AI (Anthropic)
            </span>
            <span className="text-[var(--inner-ink)]">{anthropicConfigured ? "Configured" : "Not configured (deterministic fallback only)"}</span>
          </div>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={true} />
              Analytics
            </span>
            <span className="text-[var(--inner-ink)]">First-party (Event table) — no external provider connected</span>
          </div>
          <div className={row}>
            <span className="flex items-center text-[var(--inner-ink-soft)]">
              <StatusDot ok={cronConfigured} />
              Scheduled jobs (CRON_SECRET)
            </span>
            <span className="text-[var(--inner-ink)]">{cronConfigured ? "Configured" : "Not configured — run jobs manually from Analytics"}</span>
          </div>
          <div className={row}>
            <span className="text-[var(--inner-ink-soft)]">Report PDF storage</span>
            <span className="text-[var(--inner-ink)]">Generated on demand — no persistent object storage configured</span>
          </div>
        </div>
      </div>

      <div className={card}>
        <p className={label}>Backup</p>
        <p className="mb-3 text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
          No automated backup is configured for this environment. This is a plain honest status, not a placeholder for
          something that secretly exists — if this matters for your deployment, a real setup needs: (1) scheduled
          Postgres snapshots (e.g. your host&apos;s point-in-time recovery or a pg_dump cron), (2) a retention policy,
          and (3) a tested restore procedure documented somewhere your team can find it under pressure.
        </p>
        <div className={row}>
          <span className="text-[var(--inner-ink-soft)]">Last database backup</span>
          <span className="text-[var(--inner-ink)]">Not configured</span>
        </div>
        <div className={row}>
          <span className="text-[var(--inner-ink-soft)]">Backup status</span>
          <span className="text-[var(--inner-ink)]">No automation in place</span>
        </div>
      </div>
    </div>
  );
}
