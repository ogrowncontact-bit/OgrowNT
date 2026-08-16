import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/adminAuth";
import { getAllOrdersForExport } from "@/lib/admin/analyticsReader";

function csvCell(value: string | number): string {
  const str = String(value);
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
}

export async function GET() {
  await requireAdmin();

  const orders = await getAllOrdersForExport();
  const header = ["order_id", "date", "email", "experience", "product", "amount", "currency", "status"];
  const rows = orders.map((o) =>
    [
      o.id,
      o.createdAt.toISOString(),
      o.email,
      o.assessmentName,
      o.productType,
      (o.amountCents / 100).toFixed(2),
      o.currency,
      o.status,
    ]
      .map(csvCell)
      .join(",")
  );
  const csv = [header.join(","), ...rows].join("\n");

  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="inner-orders-${new Date().toISOString().slice(0, 10)}.csv"`,
    },
  });
}
