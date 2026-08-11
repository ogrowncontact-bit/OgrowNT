"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { changePlan, getSubscription, listPlans, startCheckout } from "@/lib/billing";
import type { Plan, Subscription, SubscriptionStatus } from "@/lib/types";

const STATUS_LABELS: Record<SubscriptionStatus, string> = {
  TRIALING: "Periodo de teste",
  ACTIVE: "Ativa",
  PAST_DUE: "Pagamento pendente",
  CANCELED: "Cancelada",
};

const STATUS_COLORS: Record<SubscriptionStatus, string> = {
  TRIALING: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  ACTIVE: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  PAST_DUE: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  CANCELED: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
};

function formatMoney(value: string, currency: string): string {
  const n = Number(value);
  return `${currency} ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function daysUntil(iso: string): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));
}

export function BillingView({ businessId, token }: { businessId: string; token: string }) {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [sub, planList] = await Promise.all([getSubscription(businessId, token), listPlans()]);
    setSubscription(sub);
    setPlans(planList);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [sub, planList] = await Promise.all([getSubscription(businessId, token), listPlans()]);
        if (!cancelled) {
          setSubscription(sub);
          setPlans(planList);
        }
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar os dados de assinatura.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token]);

  async function handleChangePlan(planKey: string) {
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      await changePlan(businessId, token, planKey);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel trocar de plano.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCheckout() {
    setError(null);
    setInfo(null);
    try {
      await startCheckout(businessId, token);
    } catch (err) {
      // Esperado: o checkout online e um stub honesto (501) - a mensagem do
      // backend ja explica que o pagamento hoje e manual.
      setInfo(err instanceof ApiError ? err.message : "Nao foi possivel iniciar o pagamento.");
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Assinatura</h1>

      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      {info && <p className="mb-3 max-w-2xl text-sm text-blue-700 dark:text-blue-400">{info}</p>}
      {!subscription && !error && <p className="text-sm text-zinc-400">Carregando...</p>}

      {subscription && (
        <div className="mb-6 max-w-2xl rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Plano atual: {subscription.plan.name}</p>
              <p className="text-xs text-zinc-400">
                {formatMoney(subscription.plan.priceMonthly, subscription.plan.currency)}/mes
                {Number(subscription.plan.setupFee) > 0
                  ? ` + taxa de configuracao ${formatMoney(subscription.plan.setupFee, subscription.plan.currency)}`
                  : ""}
              </p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_COLORS[subscription.status]}`}>
              {STATUS_LABELS[subscription.status]}
            </span>
          </div>

          {subscription.status === "TRIALING" && (
            <p className="mt-3 text-xs text-zinc-500">
              Faltam {daysUntil(subscription.trialEndsAt)} dia(s) do primeiro mes gratis.
            </p>
          )}

          {Number(subscription.plan.setupFee) > 0 && (
            <>
              <p className="mt-1 text-xs text-zinc-500">
                Taxa de configuracao: {subscription.setupFeePaid ? "paga" : "pendente"}
              </p>
              {!subscription.setupFeePaid && (
                <button
                  onClick={handleCheckout}
                  className="mt-3 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-50 dark:text-zinc-900"
                >
                  Pagar taxa de configuracao
                </button>
              )}
            </>
          )}
        </div>
      )}

      {plans.length > 0 && (
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Planos disponiveis</h2>
          <div className="grid max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
            {plans.map((plan) => {
              const isCurrent = subscription?.plan.key === plan.key;
              return (
                <div
                  key={plan.id}
                  className={`rounded-lg border p-4 ${
                    isCurrent ? "border-zinc-900 dark:border-zinc-100" : "border-zinc-200 dark:border-zinc-800"
                  }`}
                >
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{plan.name}</p>
                  <p className="text-xs text-zinc-400">{formatMoney(plan.priceMonthly, plan.currency)}/mes</p>
                  {isCurrent ? (
                    <span className="mt-2 inline-block text-xs text-zinc-400">Plano atual</span>
                  ) : (
                    <button
                      onClick={() => handleChangePlan(plan.key)}
                      disabled={busy}
                      className="mt-2 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium disabled:opacity-50 dark:border-zinc-700"
                    >
                      Mudar para este plano
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
