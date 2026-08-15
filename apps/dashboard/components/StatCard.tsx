export function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "positive" | "negative";
}) {
  const toneClass =
    tone === "positive" ? "text-signal-green" : tone === "negative" ? "text-signal-red" : "text-ink-100";

  return (
    <div className="rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-1 text-[11px] uppercase tracking-wider text-ink-500">{label}</p>
      <p className={`text-xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}
