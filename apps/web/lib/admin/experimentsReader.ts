import { prisma } from "@inner/db";

export interface ExperimentVariantResult {
  experimentId: string;
  variant: string;
  exposed: number;
  converted: number;
  conversionPct: number;
}

/**
 * Reads whatever experiment_exposure events exist — works generically off
 * the event log rather than lib/experiments.ts's EXPERIMENTS list, so it
 * still reports correctly on historical experiments that have since been
 * removed from that config. "Converted" = the same anonymous session later
 * fired payment_completed, matching the spec's own paywall-headline
 * example (conversion means purchase here, not just click-through).
 */
export async function getExperimentResults(): Promise<ExperimentVariantResult[]> {
  const [exposures, purchases] = await Promise.all([
    prisma.event.findMany({
      where: { eventName: "experiment_exposure" },
      select: { anonymousSessionId: true, occurredAt: true, properties: true },
      orderBy: { occurredAt: "asc" },
    }),
    prisma.event.findMany({
      where: { eventName: "payment_completed" },
      select: { anonymousSessionId: true, occurredAt: true },
    }),
  ]);

  const firstPurchaseBySession = new Map<string, Date>();
  for (const p of purchases) {
    const existing = firstPurchaseBySession.get(p.anonymousSessionId);
    if (!existing || p.occurredAt < existing) firstPurchaseBySession.set(p.anonymousSessionId, p.occurredAt);
  }

  // Earliest exposure per (session, experiment) only — a session re-exposed to the same experiment shouldn't be double-counted.
  const seenPerExperiment = new Map<string, Set<string>>();
  const buckets = new Map<string, { exposed: number; converted: number }>();

  for (const e of exposures) {
    const props = e.properties as { experimentId?: string; variant?: string } | null;
    if (!props?.experimentId || !props?.variant) continue;

    const seenKey = props.experimentId;
    const seen = seenPerExperiment.get(seenKey) ?? new Set<string>();
    if (seen.has(e.anonymousSessionId)) continue;
    seen.add(e.anonymousSessionId);
    seenPerExperiment.set(seenKey, seen);

    const bucketKey = `${props.experimentId}::${props.variant}`;
    const bucket = buckets.get(bucketKey) ?? { exposed: 0, converted: 0 };
    bucket.exposed += 1;
    const purchaseAt = firstPurchaseBySession.get(e.anonymousSessionId);
    if (purchaseAt && purchaseAt >= e.occurredAt) bucket.converted += 1;
    buckets.set(bucketKey, bucket);
  }

  return [...buckets.entries()]
    .map(([key, b]) => {
      const [experimentId, variant] = key.split("::");
      return {
        experimentId,
        variant,
        exposed: b.exposed,
        converted: b.converted,
        conversionPct: b.exposed > 0 ? Math.round((b.converted / b.exposed) * 1000) / 10 : 0,
      };
    })
    .sort((a, b) => a.experimentId.localeCompare(b.experimentId) || a.variant.localeCompare(b.variant));
}
