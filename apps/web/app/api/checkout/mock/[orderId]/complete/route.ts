import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { isMockPayments } from "@/lib/payments";
import { completeOrder } from "@/lib/commerce";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  if (!isMockPayments()) return NextResponse.json({ error: "Not available" }, { status: 403 });

  const { orderId } = await params;
  const order = await prisma.order.findUnique({ where: { id: orderId }, include: { assessmentSession: true } });
  if (!order) return NextResponse.json({ error: "Order not found" }, { status: 404 });

  await completeOrder(orderId);

  return NextResponse.json({
    reportUrl: `/${order.assessmentSession.sourceSlug}/session/${order.assessmentSessionId}/report`,
  });
}
