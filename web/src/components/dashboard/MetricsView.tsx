"use client";

import { useEffect, useState } from "react";
import { getMetrics } from "@/lib/metrics";
import type { BookingStatus, Metrics } from "@/lib/types";

const PERIODS = [
  { days: 7, label: "7 dias" },
  { days: 30, label: "30 dias" },
  { days: 90, label: "90 dias" },
];

const STATUS_LABELS: Record<BookingStatus, string> = {
  PENDING: "Pendentes",
  CONFIRMED: "Confirmadas",
  CANCELLED: "Canceladas",
  COMPLETED: "Concluidas",
  NO_SHOW: "Nao compareceu",
};

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-400">{title}</h3>
      {children}
    </div>
  );
}

function BigNumber({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <p className="text-3xl font-semibold text-zinc-900 dark:text-zinc-50">{value}</p>
      <p className="text-xs text-zinc-400">{label}</p>
    </div>
  );
}

export function MetricsView({ businessId, token }: { businessId: string; token: string }) {
  const [days, setDays] = useState(30);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setMetrics(null);
      setError(null);
      try {
        const data = await getMetrics(businessId, token, days);
        if (!cancelled) setMetrics(data);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar as metricas.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token, days]);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Dashboard</h1>
        <div className="flex gap-1 rounded-md bg-zinc-100 p-1 dark:bg-zinc-900">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setDays(p.days)}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                days === p.days
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-50"
                  : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {!metrics && !error && <p className="text-sm text-zinc-400">Carregando...</p>}

      {metrics && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card title="Conversas">
            <div className="grid grid-cols-2 gap-4">
              <BigNumber value={metrics.conversations.total} label="No periodo" />
              <BigNumber value={formatPercent(metrics.conversations.aiResolvedRate)} label="Resolvidas so pela IA" />
            </div>
            <p className="mt-3 text-xs text-zinc-400">
              {metrics.conversations.needingHumanNow} precisando de atendimento agora
            </p>
          </Card>

          <Card title="Reservas">
            <div className="grid grid-cols-2 gap-4">
              <BigNumber value={metrics.bookings.total} label="No periodo" />
              <BigNumber value={metrics.bookings.upcomingConfirmed} label="Confirmadas, a acontecer" />
            </div>
            <ul className="mt-3 space-y-1 text-xs text-zinc-500">
              {(Object.keys(STATUS_LABELS) as BookingStatus[]).map((status) => (
                <li key={status} className="flex justify-between">
                  <span>{STATUS_LABELS[status]}</span>
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">{metrics.bookings.byStatus[status]}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Ferramentas de IA">
            <div className="grid grid-cols-2 gap-4">
              <BigNumber value={metrics.toolCalls.total} label="Chamadas no periodo" />
              <BigNumber value={formatPercent(metrics.toolCalls.successRate)} label="Taxa de sucesso" />
            </div>
          </Card>

          <Card title="Mensagens">
            <div className="grid grid-cols-2 gap-4">
              <BigNumber value={metrics.messages.in} label="Recebidas" />
              <BigNumber value={metrics.messages.out} label="Enviadas" />
            </div>
          </Card>

          <Card title="Servicos mais reservados">
            {metrics.topServices.length === 0 ? (
              <p className="text-sm text-zinc-400">Nenhuma reserva no periodo.</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {metrics.topServices.map((s) => (
                  <li key={s.serviceId} className="flex justify-between text-zinc-700 dark:text-zinc-300">
                    <span className="truncate">{s.name}</span>
                    <span className="font-medium">{s.bookings}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
