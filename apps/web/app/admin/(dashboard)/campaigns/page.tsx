import { listCampaignsForAdmin } from "@/lib/admin/campaignsReader";
import { listAssessmentsForAdmin } from "@/lib/admin/catalogReader";
import { CampaignManager } from "@/components/admin/CampaignManager";
import { UtmBuilder } from "@/components/admin/UtmBuilder";
import { getSiteUrl } from "@/lib/siteUrl";

export const dynamic = "force-dynamic";

export default async function AdminCampaignsPage() {
  const [campaigns, assessments] = await Promise.all([listCampaignsForAdmin(), listAssessmentsForAdmin()]);

  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">Campaign Center</h1>

      <div className="mb-8">
        <UtmBuilder siteUrl={getSiteUrl()} landingSlugs={assessments.map((a) => a.slug)} />
      </div>

      <CampaignManager
        campaigns={campaigns}
        assessments={assessments.map((a) => ({ id: a.id, name: a.name, slug: a.slug }))}
      />
    </div>
  );
}
