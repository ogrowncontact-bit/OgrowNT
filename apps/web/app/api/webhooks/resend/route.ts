import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { verifySvixSignature } from "@/lib/security/svixWebhook";

/**
 * Delivery-status callback from Resend — updates the EmailEvent row a send
 * already created (matched by providerRef = Resend's email id) so
 * /admin/email can show delivered/bounced, not just "we called send()".
 * Unreachable/no-op while RESEND_WEBHOOK_SECRET isn't configured (dev, or
 * LocalProvider is active) — see docs on getEmailProvider().
 */
export async function POST(request: NextRequest) {
  const secret = process.env.RESEND_WEBHOOK_SECRET;
  if (!secret) return NextResponse.json({ error: "Webhook not configured" }, { status: 404 });

  const rawBody = await request.text();
  const verified = verifySvixSignature({
    secret,
    svixId: request.headers.get("svix-id"),
    svixTimestamp: request.headers.get("svix-timestamp"),
    svixSignature: request.headers.get("svix-signature"),
    rawBody,
  });
  if (!verified) return NextResponse.json({ error: "Invalid signature" }, { status: 400 });

  const event = JSON.parse(rawBody) as { type?: string; data?: { email_id?: string } };
  const emailId = event.data?.email_id;
  if (!emailId) return NextResponse.json({ ok: true }); // nothing to correlate against

  const emailEvent = await prisma.emailEvent.findFirst({ where: { providerRef: emailId } });
  if (!emailEvent) return NextResponse.json({ ok: true }); // e.g. a send we don't track (none currently, but future-proof)

  switch (event.type) {
    case "email.delivered":
      await prisma.emailEvent.update({ where: { id: emailEvent.id }, data: { status: "delivered", deliveredAt: new Date() } });
      break;
    case "email.bounced":
      await prisma.emailEvent.update({ where: { id: emailEvent.id }, data: { status: "bounced", bouncedAt: new Date() } });
      break;
    case "email.opened":
      await prisma.emailEvent.update({ where: { id: emailEvent.id }, data: { openedAt: new Date() } });
      break;
    case "email.clicked":
      await prisma.emailEvent.update({ where: { id: emailEvent.id }, data: { clickedAt: new Date() } });
      break;
    default:
      break; // email.sent / email.delivery_delayed / email.complained — no column to reflect yet
  }

  return NextResponse.json({ ok: true });
}
