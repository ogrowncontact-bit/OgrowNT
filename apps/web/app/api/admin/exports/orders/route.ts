import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/adminAuth";
import { getAllOrdersForExport } from "@/lib/admin/analyticsReader";

// Neutralizes CSV/formula injection (CWE-1236): a cell starting with =, +, -, @,
// tab, or CR is interpreted as a formula by Excel/Sheets regardless of quoting.
// order.user.email is end-user-submitted at checkout and only loosely validated,
// so it must never reach a spreadsheet-opened export unescaped.
function csvCell(value: string | number): string {
  let str = String(value);
  if (/^[=+\-@\t\r]/.test(str)) str = `'${str}`;
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
