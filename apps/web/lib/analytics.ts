import { prisma } from "@inner/db";

export interface TrackParams {
  anonymousSessionId: string;
  eventName: string;
  assessmentId?: string;
  userId?: string;
  properties?: Record<string, unknown>;
  utm?: {
    utmSource?: string;
    utmMedium?: string;
    utmCampaign?: string;
    utmContent?: string;
    utmTerm?: string;
  };
}

/** Server-side event write — see docs/ARCHITECTURE.md §11. Never pass raw answer text in `properties`. */
export async function track(params: TrackParams): Promise<void> {
  await prisma.event.create({
    data: {
      anonymousSessionId: params.anonymousSessionId,
      eventName: params.eventName,
      assessmentId: params.assessmentId,
      userId: params.userId,
      properties: params.properties as any,
      utmSource: params.utm?.utmSource,
      utmMedium: params.utm?.utmMedium,
      utmCampaign: params.utm?.utmCampaign,
      utmContent: params.utm?.utmContent,
      utmTerm: params.utm?.utmTerm,
    },
  });
}
