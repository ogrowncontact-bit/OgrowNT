import type { EquityPoint } from "@/lib/api";

export function EquitySparkline({ points }: { points: EquityPoint[] }) {
  if (points.length < 2) {
    return <p className="text-xs text-ink-500">Not enough snapshots yet to draw a curve.</p>;
  }

  const width = 480;
  const height = 80;
  const values = points.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p.equity - min) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const last = points[points.length - 1];
  const first = points[0];
  const trendUp = last.equity >= first.equity;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-20 w-full" preserveAspectRatio="none">
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke={trendUp ? "#3ecf8e" : "#e5484d"}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
