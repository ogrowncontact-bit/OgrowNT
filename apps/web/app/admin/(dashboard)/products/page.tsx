import Link from "next/link";
import { listProductsForAdmin } from "@/lib/admin/productsReader";
import { formatPrice } from "@/lib/money";

export const dynamic = "force-dynamic";

export default async function AdminProductsPage() {
  const products = await listProductsForAdmin();

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Products</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Every priced product across all discoveries. Prices are edited per-discovery in its own Pricing section —{" "}
        <Link href="/refund" className="underline">refund policy</Link> applies to all of them.
      </p>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Discovery</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Product</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Price</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Market (currency)</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Edit</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{p.assessmentName}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{p.productType}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatPrice(p.amountCents, p.currency)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{p.currency}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  <span className={p.active ? "text-[var(--inner-accent)]" : "text-[var(--inner-muted)]"}>
                    {p.active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <Link href={`/admin/assessments/${p.assessmentId}`} className="underline text-[var(--inner-ink-soft)]">
                    Edit →
                  </Link>
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No products configured yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
