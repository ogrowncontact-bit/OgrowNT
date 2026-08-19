import { prisma } from "@inner/db";

export interface RecordEmailEventParams {
  userId: string;
  type: string;
  templateKey: string;
  /** Marketing (campaign) sends only — everything else (report delivery, purchase confirmation, magic links, refunds...) is triggered by the recipient's own action and stays transactional regardless of marketing consent. */
  transactional?: boolean;
  providerRef?: string;
  /** Report.id or Order.id depending on `type` — see the schema comment on EmailEvent.relatedEntityId. Lets a customer with more than one purchase be retried against the right one. */
  relatedEntityId?: string;
  status?: "sent" | "failed";
  failureReason?: string;
}

/**
 * The one place every transactional/marketing send writes its delivery
 * record — feeds /admin/email and the Resend delivered/bounced webhook
 * (see app/api/webhooks/resend/route.ts, which updates a row by
 * providerRef). Never throws: a broken delivery-tracking write must not
 * break the send it's recording, matching lib/analytics.ts's track().
 */
export async function recordEmailEvent(params: RecordEmailEventParams): Promise<void> {
  try {
    await prisma.emailEvent.create({
      data: {
        userId: params.userId,
        type: params.type,
        templateKey: params.templateKey,
        transactional: params.transactional ?? true,
        providerRef: params.providerRef,
        relatedEntityId: params.relatedEntityId,
        status: params.status ?? "sent",
        failureReason: params.failureReason,
      },
    });
  } catch (error) {
    console.error(`[email-events] failed to record "${params.type}" for user ${params.userId}`, error);
  }
}
