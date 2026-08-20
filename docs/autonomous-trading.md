# Autonomous Paper Trading ("PROMPT 8")

## TradingMode and the safety gate order

Every new position goes through the same ordered gate in
`packages/risk/engine.py::evaluate_signal`, each step able to only block or
shrink a signal, never approve one on its own:

```
trading_enabled (Kill Switch)
  → trading_paused (PAUSE — voluntary, distinct from the Kill Switch)
  → trading_mode == 'paper' (TradingMode gate — LIVE never functionally exists this phase)
  → short-selling honesty fallback (asset_class == 'equity' && direction == 'short' → blocked)
  → safety belt tier floor
  → data quality / staleness
  → risk/reward minimum
  → portfolio exposure / single-asset concentration / correlation cluster
  → loss limits (daily/weekly/monthly) / drawdown belt
  → strategy health
  → news risk
  → loss streak (size only)
  → leverage ceiling assertion
  → position sizing
```

Then, **after** Risk Engine approval, `apps/worker/risk_execution.py` runs a
second, independent gate: `packages/portfolio/manager.py::evaluate_allocation`
(the Portfolio Manager) checks per-strategy capital allocation
(`max_strategy_allocation_pct`), the one concentration axis the Risk
Engine's own per-asset/correlation checks don't cover. Only after **both**
gates approve does `packages/execution/order_manager.py::open_position` run.

`SystemState.trading_mode` can only ever be `'paper'` or `'live_disabled'`
— no code path in this repository writes anything else. There are no
broker API keys, no exchange trading keys, no withdrawal permissions
anywhere in this codebase. `# ZERO live trading`.

## Position lifecycle and the HOLD/REDUCE/CLOSE policy

A position always has a mandatory stop (`Position.current_stop`, set from
the originating signal — no signal without a valid stop reaches
`open_position` at all) and an optional target
(`Position.target_price`). Every cycle, `apps/worker/trade_monitor.py`:

1. Updates the trailing stop if `Position.trailing_stop_config` is set
   (`packages/quant/exits/trailing_stop.py` — `fixed_distance` /
   `percentage` / `atr_based`; never widens a stop).
2. Checks stop/target — unconditional, the strategy's own declared risk
   boundary.
3. If neither hit, checks three triggers in severity order and, if any
   fires, asks `packages/risk/position_policy.py::evaluate_position_risk_event`
   what to do — **never** acts unilaterally:
   - Portfolio emergency: Kill Switch active, or safety belt at
     `EMERGENCY`.
   - Critical news (`packages/risk/news_guard.py`'s global level ==
     `critical`).
   - Regime shift into the strategy's declared `worst_regimes`.

The policy per trigger (`config/risk_limits.yaml`'s
`position_risk_policy`) is `hold` / `reduce` / `close` — an explicit,
operator-tunable choice, never inferred behavior. `reduce` partially
closes the position via `packages/execution/order_manager.py::reduce_position`
(a configurable fraction, `reduce_fraction`) — the remainder stays open,
untouched, at its existing stop/target. A REDUCE deliberately skips the
Learning Agent side effects (Pattern Memory, Strategy Health, Quarantine,
Trade Journal) a full close triggers — it isn't a strategy-driven exit.

## Anti-martingale

`packages/risk/loss_streak.py::evaluate_loss_streak` halves new position
size after 5 consecutive portfolio-wide losses (`loss_streak.threshold` in
`config/risk_limits.yaml`) — and that's the *only* direction it moves
size. No code path anywhere reads past P&L to increase size after a loss
or a win streak; `tests/test_risk_loss_streak.py::test_win_streak_never_increases_size`
proves it behaviorally.

## Idempotency and execution quality

Every `Order` carries an `idempotency_key`
(`{purpose}:{position_or_signal_id}:{attempt_number}`, unique in the DB).
A signal is only ever submitted once (each strategy cycle mints a fresh
`Signal` row), so `open:{signal_id}:0` never collides. A close/reduce
attempt counts how many `Order` rows already exist for the position — a
legitimate next-cycle retry after a `DATA_UNAVAILABLE` rejection gets a
fresh key; two callers racing on the exact same attempt compute the same
key and the second INSERT hits the unique constraint instead of placing a
duplicate real order.

`Order.expected_price` (the signal's entry price, or the price that
triggered a close/reduce) and `Order.latency_ms` (decision → fill) are
captured on every submission — the raw data behind "expected vs. actual"
execution-quality measurement.

## Event sourcing and the decision trace

`TradingEvent` rows (`order_submitted/filled/rejected`,
`position_opened/closed`, `risk_blocked`, `no_trade`,
`trading_paused/resumed`, `kill_switch_triggered/released`,
`reconciliation_mismatch`, `portfolio_emergency_action`,
`loss_streak_detected`, `worker_restarted`,
`crash_loop_protection_triggered`) are the backing store for
`GET /api/trading/activity` — the dashboard's Live Activity Feed. This
complements, not replaces, the per-signal detail already in
`RiskCheck`/`RiskDecision` (the "WHY did the system trade / not trade?"
answer for one specific signal — see `GET /api/trades/{id}/why`,
Phase 3) and `AuditLog` (admin/system actions).

## Reconciliation

`packages/portfolio/reconciliation.py::run_reconciliation` reconstructs
cash from first principles — initial capital, minus every entry fee ever
paid, minus notional tied up in currently-open positions, plus every
trade's realized P&L — and compares it against the incrementally
maintained ledger (`packages/portfolio/state.py`). It also checks
cash ≥ 0, every open position's size > 0, and every fee ≥ 0. Any
violation calls `reconcile_and_enforce`, which sets
`SystemState.trading_paused = True` (an accounting-integrity stop, never
the Kill Switch) and writes a critical `Alert` — once per failure streak,
not on every subsequent tick. Runs every `reconciliation_interval_seconds`
(default 300s) in `apps/worker/main.py`.

## System health and crash-loop protection

`packages/shared/worker_health.py::record_system_health_snapshot` writes a
`SystemHealth` row every `health_snapshot_interval_seconds` (default
300s) — a persisted history `GET /api/system/health`'s on-demand view
doesn't keep. `compute_autonomous_status` derives one of `starting` /
`running` / `paused` / `caution` / `defensive` / `emergency` /
`kill_switch` / `error`, shared between that snapshot and
`GET /api/trading/status` so the two can never disagree. `NO_TRADE` is
deliberately not one of the persisted values — it's a per-decision fact
(the `no_trade` `TradingEvent`), not something derivable from
`SystemState` alone without fabricating meaning from data that doesn't
support it.

`record_worker_restart` (called once at every `apps/worker/main.py`
process start) counts restarts within a rolling window
(`max_worker_restarts_per_window`, `restart_window_seconds`) and
auto-pauses trading if exceeded — Docker's `restart: unless-stopped`
already restarts a crashed process at the OS level; this stops a silently
crash-looping process from keeping trading "on" underneath the flapping.

## Manual controls

All admin-only (`require_admin_role` — see RBAC below), each writing a
`ManualAction` row with a full before/after snapshot:

| Action | Endpoint |
|---|---|
| PAUSE | `POST /api/trading/pause` `{reason}` |
| RESUME | `POST /api/trading/resume` |
| CLOSE PAPER POSITION | `POST /api/trading/positions/{id}/close` `{reason?}` |
| CANCEL PAPER ORDER | `POST /api/trading/orders/{id}/cancel` `{reason?}` |
| ACTIVATE / RELEASE KILL SWITCH | `POST /api/system/kill-switch` / `/kill-switch/release` (Phase 3, unchanged) |
| RESET PAPER ACCOUNT | `POST /api/trading/reset-paper` `{confirm: true}` |

`RESET PAPER ACCOUNT` requires `confirm: true` and refuses while any
position is open. It sets `SystemState.last_reset_at`; every
`PortfolioSnapshot`/`Order`/`Trade` before that instant stays in the
database untouched (append-only, fully auditable) but stops counting
toward peak-equity/drawdown/period-P&L in
`packages/portfolio/state.py` and toward
`packages/portfolio/reconciliation.py`'s ledger reconstruction — without
this, a reset would immediately read as a huge fake drawdown against a
peak from a life the account no longer has.

`CANCEL PAPER ORDER` is fully implemented and tested, but in this
architecture `PaperExecutionProvider` fills market orders synchronously —
no `Order` ever actually sits in `new`/`submitted` long enough to cancel
today. Honest limitation, not hidden: the endpoint is ready for whenever a
future order type or provider produces a real pending state.

## RBAC

`AdminUser.role` is `admin` or `viewer`. Every read endpoint accepts
either (`get_current_admin`); every mutation — manual controls, Kill
Switch, `PATCH /api/system/risk-limits` — requires `admin`
(`require_admin_role`). `POST /api/auth/users` (admin-only) creates a
`viewer` account so the operator can hand out a read-only link without
sharing the admin password.

## Running a real multi-day soak test

The automated suite (`tests/test_crash_recovery_and_continuous_simulation.py`)
compresses the §67 24h/72h/7-day soak test into ~15 rapid cycles inside one
process — enough to prove state persistence, reconciliation stability, and
idempotency-key uniqueness hold across many cycles, without making the
test suite itself take days to run. For a literal long-duration run, start
the real stack (`docker compose up`, or `uvicorn`+`python -m apps.worker.main`
directly) and let it run against the mock market data provider for the
desired duration, then check:

- `GET /api/system/health` and `GET /api/trading/status` stay green/`running`
- `GET /api/trading/activity` keeps advancing (the worker is still doing something)
- `packages/portfolio/reconciliation.run_reconciliation(db)` stays `ok=True`
- Postgres memory/connection counts stay flat (no leak)
- The container's own memory usage (`docker stats`) stays flat
