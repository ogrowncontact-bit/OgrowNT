import type { CorrelationPair, ExposureItem } from "@/lib/api";

// Concentration heatmap — docs/blueprint/08-risk-engine.md#concentration-guard,
// Prompt 4 §31. Cell intensity is pct_of_equity (asset/strategy/direction) or
// |correlation| (pairs) mapped onto the same green->red scale the rest of the
// dashboard uses for risk severity, so a glance tells you where concentration
// risk is building without reading numbers.
function intensityColor(pct: number): string {
  if (pct >= 20) return "bg-signal-red/70 text-ink-100";
  if (pct >= 12) return "bg-signal-red/35 text-ink-100";
  if (pct >= 6) return "bg-signal-yellow/35 text-ink-100";
  if (pct > 0) return "bg-signal-green/25 text-ink-100";
  return "bg-base-800 text-ink-500";
}

function ExposureRow({ label, items }: { label: string; items: ExposureItem[] }) {
  if (items.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="w-20 shrink-0 text-ink-500">{label}</span>
        <span className="text-ink-500">no open exposure</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-ink-500">{label}</span>
      <div className="flex flex-1 flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item.key}
            className={`rounded px-2 py-1 font-medium ${intensityColor(item.pct_of_equity)}`}
            title={`${item.key}: ${item.pct_of_equity.toFixed(2)}% of equity`}
          >
            {item.key} {item.pct_of_equity.toFixed(1)}%
          </span>
        ))}
      </div>
    </div>
  );
}

export function RiskHeatmap({
  byAsset,
  byStrategy,
  byDirection,
  correlations,
}: {
  byAsset: ExposureItem[];
  byStrategy: ExposureItem[];
  byDirection: ExposureItem[];
  correlations: CorrelationPair[];
}) {
  return (
    <div className="space-y-2">
      <ExposureRow label="Asset" items={byAsset} />
      <ExposureRow label="Strategy" items={byStrategy} />
      <ExposureRow label="Direction" items={byDirection} />
      <div className="flex items-start gap-2 text-xs">
        <span className="w-20 shrink-0 pt-1 text-ink-500">Correlation</span>
        {correlations.length > 0 ? (
          <div className="flex flex-1 flex-wrap gap-1.5">
            {correlations.map((pair) => (
              <span
                key={`${pair.asset_symbol_a}-${pair.asset_symbol_b}`}
                className={`rounded px-2 py-1 font-medium ${intensityColor(Math.abs(pair.correlation) * 100)}`}
                title={`computed ${new Date(pair.ts).toLocaleString()}`}
              >
                {pair.asset_symbol_a}/{pair.asset_symbol_b} {pair.correlation.toFixed(2)}
              </span>
            ))}
          </div>
        ) : (
          <span className="pt-1 text-ink-500">
            No correlation data yet for currently held assets — the worker computes this on the
            strategy cadence (docs/blueprint/08-risk-engine.md#correlation-guard).
          </span>
        )}
      </div>
    </div>
  );
}
