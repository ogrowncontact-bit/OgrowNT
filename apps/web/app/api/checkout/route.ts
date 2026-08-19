import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { SUPPORTED_REPORT_LANGUAGES } from "@inner/ai";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { getPaymentProvider } from "@/lib/payments";
import { track } from "@/lib/analytics";

function appBaseUrl(request: NextRequest): string {
  return process.env.APP_BASE_URL ?? request.nextUrl.origin;
}

/** Explicit selection (future language switcher) wins over Accept-Language; falls back to English rather than guessing. */
function resolveReportLanguage(explicit: string | undefined, acceptLanguageHeader: string | null): string {
  const supported = SUPPORTED_REPORT_LANGUAGES as readonly string[];
  if (explicit && supported.includes(explicit)) return explicit;

  const candidates = (acceptLanguageHeader ?? "").split(",").map((part) => part.trim().split(";")[0]?.slice(0, 2).toLowerCase());
  return candidates.find((c) => c && supported.includes(c)) ?? "en";
}

export async function POST(request: NextRequest) {
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const body = await request.json().catch(() => null);
  const assessmentSessionId = body?.assessmentSessionId as string | undefined;
  const email = (body?.email as string | undefined)?.trim().toLowerCase();
  const marketingConsent = body?.marketingConsent === true;
  const consentVersion = (body?.consentVersion as string | undefined) ?? "v1";

  if (!assessmentSessionId || !email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: "A valid email is required" }, { status: 400 });
  }

  const session = await prisma.assessmentSession.findUnique({ where: { id: assessmentSessionId } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  if (session.status !== "completed") {
    return NextResponse.json({ error: "Assessment isn't finished yet" }, { status: 409 });
  }

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) return NextResponse.json({ error: "Unknown assessment" }, { status: 500 });

  // Already purchased — don't charge twice.
  const existingEntitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId } });
  if (existingEntitlement) {
    return NextResponse.json({
      checkoutUrl: `${appBaseUrl(request)}/${session.sourceSlug}/session/${assessmentSessionId}/report`,
    });
  }

  const user = await prisma.user.upsert({
    where: { email },
    update: {},
    create: { email },
  });

  await prisma.anonymousSession.update({ where: { id: anonymousSessionId }, data: { userId: user.id } });

  const anonymous = await prisma.anonymousSession.findUnique({ where: { id: anonymousSessionId } });

  await prisma.marketingConsent.create({
    data: {
      userId: user.id,
      consent: marketingConsent,
      consentVersion,
      consentSource: `checkout:${session.sourceSlug}`,
      campaign: anonymous?.utmCampaign,
      assessmentId: session.assessmentId,
    },
  });

  await track({ anonymousSessionId, eventName: "email_submitted", assessmentId: session.assessmentId, userId: user.id });

  const price = await prisma.price.findFirst({
    where: { assessmentId: session.assessmentId, productType: "individual", active: true },
  });
  if (!price) return NextResponse.json({ error: "No active price for this assessment" }, { status: 500 });

  const language = resolveReportLanguage(body?.language as string | undefined, request.headers.get("accept-language"));

  const order = await prisma.order.create({
    data: {
      userId: user.id,
      assessmentSessionId,
      priceId: price.id,
      amountCents: price.amountCents,
      currency: price.currency,
      status: "pending",
      provider: getPaymentProvider().name,
      language,
    },
  });

  const checkoutSession = await getPaymentProvider().createCheckoutSession({
    orderId: order.id,
    amountCents: price.amountCents,
    currency: price.currency,
    productName: `${config.name} — Personal Report`,
    customerEmail: email,
    successUrl: `${appBaseUrl(request)}/${session.sourceSlug}/session/${assessmentSessionId}/report?checkout=success`,
    cancelUrl: `${appBaseUrl(request)}/${session.sourceSlug}/session/${assessmentSessionId}/paywall?payment=failed`,
  });

  await prisma.order.update({ where: { id: order.id }, data: { providerRef: checkoutSession.providerRef } });
  await track({
    anonymousSessionId,
    eventName: "checkout_started",
    assessmentId: session.assessmentId,
    userId: user.id,
    properties: { orderId: order.id, productId: price.id, priceId: price.id, currency: price.currency, amountCents: price.amountCents },
    utm: {
      utmSource: anonymous?.utmSource ?? undefined,
      utmMedium: anonymous?.utmMedium ?? undefined,
      utmCampaign: anonymous?.utmCampaign ?? undefined,
      utmContent: anonymous?.utmContent ?? undefined,
      utmTerm: anonymous?.utmTerm ?? undefined,
    },
  });

  return NextResponse.json({ checkoutUrl: checkoutSession.url });
}
