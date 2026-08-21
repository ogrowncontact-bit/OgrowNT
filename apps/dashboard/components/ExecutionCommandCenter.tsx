import type { Account, Broker, Execution, ExecutionHealth, ReconciliationRun } from "@/lib/api";

// Execution Command Center — "PROMPT 13" §75-78: the Universal Broker &
// Execution Infrastructure's own dashboard surface. Deliberately does NOT
// duplicate the existing Positions/Orders/Trades tables or the Risk
// Center/Capital Defense Center panels — this covers only what's genuinely
// new this phase: registered brokers + health, account balances (the
// BrokerAdapter's own view, not the internal ledger), recent fills
// (Execution rows — "nunca assumir one order = one fill"), the broker-level
// reconciliation trend, and execution quality (fill ratio/latency/slippage).
// Live trading is never reachable regardless of what's shown here — see
// the LiveTradingFirewall note below the broker list.

const HEALTH_COLOR: Record<string, string> = {
  healthy: "text-signal-green",
  degraded: "text-signal-yellow",
  unavailable: "text-signal-red",
  quarantined: "text-signal-red",
};

function healthColor(state: string | undefined): string {
  if (!state) return "text-ink-500";
  return HEALTH_COLOR[state] ?? "text-ink-500";
}

const eur = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n);

export function ExecutionCommandCenter({
  brokers,
  brokerHealth,
  accounts,
  executions,
  reconciliationRuns,
  executionHealth,
}: {
  brokers: Broker[] | null;
  brokerHealth: Record<number, { state: string; latency_ms: number | null } | null>;
  accounts: Account[] | null;
  executions: Execution[] | null;
  reconciliationRuns: ReconciliationRun[] | null;
  executionHealth: ExecutionHealth | null;
}) {
  const latestReconciliation = (reconciliationRuns ?? [])[0] ?? null;
  const mismatchCount = (reconciliationRuns ?? []).filter((r) => !r.ok).length;

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Execution Command Center</p>
        <span className="text-[10px] uppercase text-signal-green">live trading: blocked</span>
      </div>
      <p className="mb-4 text-[10px] text-ink-500">
        Every registered broker is paper-only — the LiveTradingFirewall denies any &apos;live&apos; execution mode
        unconditionally, independent of this panel.
      </p>

      <div className="mb-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Brokers</p>
        {brokers && brokers.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {brokers.map((b) => {
              const health = brokerHealth[b.id];
              return (
                <div key={b.id} className="rounded-lg border border-base-700 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-ink-100">
                      {b.name} <span className="text-ink-500">({b.kind})</span>
                    </p>
                    <span className={`text-[10px] uppercase ${healthColor(health?.state)}`}>
                      {health?.state ?? "unknown"}
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] text-ink-500">
                    {b.is_default ? "default · " : ""}
                    {b.configured ? "credentials configured" : "no credentials configured (paper needs none)"}
                    {health?.latency_ms != null ? ` · ${health.latency_ms.toFixed(2)}ms` : ""}
                  </p>
                  <p className="mt-1 text-[10px] text-ink-500">
                    supports: {[
                      b.capabilities.supports_market_orders && "market",
                      b.capabilities.supports_limit_orders && "limit",
                      b.capabilities.supports_stop_orders && "stop",
                      b.capabilities.supports_short && "short",
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No brokers registered.</p>
        )}
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Account (broker view)</p>
          {accounts && accounts.length > 0 ? (
            accounts.map((a) => (
              <div key={a.broker_name} className="rounded-lg border border-base-700 p-3">
                <p className="text-xs text-ink-100">
                  {a.broker_name}: equity {eur(a.equity)} · cash {eur(a.balance)}
                </p>
                <p className="mt-1 text-[10px] text-ink-500">available {eur(a.available_balance)}</p>
              </div>
            ))
          ) : (
            <p className="text-xs text-ink-500">Account data unavailable.</p>
          )}
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Reconciliation {reconciliationRuns ? `(${mismatchCount} mismatch${mismatchCount === 1 ? "" : "es"} of last ${reconciliationRuns.length})` : ""}
          </p>
          {latestReconciliation ? (
            <div className="rounded-lg border border-base-700 p-3">
              <p className={`text-xs uppercase ${latestReconciliation.ok ? "text-signal-green" : "text-signal-red"}`}>
                {latestReconciliation.ok ? "OK" : "MISMATCH"} · {latestReconciliation.broker_name}
              </p>
              {!latestReconciliation.ok && (
                <ul className="mt-1 space-y-0.5">
                  {latestReconciliation.violations.slice(0, 3).map((v, i) => (
                    <li key={i} className="text-[10px] text-signal-red">
                      · {v}
                    </li>
                  ))}
                </ul>
              )}
              {latestReconciliation.balance_diff !== null && (
                <p className="mt-1 text-[10px] text-ink-500">balance_diff: {latestReconciliation.balance_diff.toFixed(4)}</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-ink-500">No reconciliation runs yet.</p>
          )}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-base-700 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Fill Ratio</p>
          <p className="text-lg font-semibold text-ink-100">
            {executionHealth?.fill_ratio != null ? `${(executionHealth.fill_ratio * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-base-700 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Avg Latency</p>
          <p className="text-lg font-semibold text-ink-100">
            {executionHealth?.avg_latency_ms != null ? `${executionHealth.avg_latency_ms.toFixed(1)}ms` : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-base-700 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Avg Slippage</p>
          <p className="text-lg font-semibold text-ink-100">
            {executionHealth?.avg_slippage_bps != null ? `${executionHealth.avg_slippage_bps.toFixed(1)}bps` : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-base-700 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Orders Evaluated</p>
          <p className="text-lg font-semibold text-ink-100">{executionHealth?.orders_evaluated ?? "—"}</p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Recent Fills</p>
        {executions && executions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-500">
                  <th className="pb-1 pr-3">Symbol</th>
                  <th className="pb-1 pr-3">Side</th>
                  <th className="pb-1 pr-3">Qty</th>
                  <th className="pb-1 pr-3">Price</th>
                  <th className="pb-1 pr-3">Fee</th>
                  <th className="pb-1">Liquidity</th>
                </tr>
              </thead>
              <tbody>
                {executions.slice(0, 10).map((e) => (
                  <tr key={e.id} className="border-t border-base-700">
                    <td className="py-1 pr-3 text-ink-100">{e.symbol}</td>
                    <td className={`py-1 pr-3 uppercase ${e.side === "buy" ? "text-signal-green" : "text-signal-red"}`}>{e.side}</td>
                    <td className="py-1 pr-3 text-ink-300">{e.quantity}</td>
                    <td className="py-1 pr-3 text-ink-300">{e.price.toFixed(4)}</td>
                    <td className="py-1 pr-3 text-ink-500">{e.fee.toFixed(4)}</td>
                    <td className="py-1 text-ink-500">{e.liquidity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No fills recorded yet.</p>
        )}
      </div>
    </section>
  );
}
