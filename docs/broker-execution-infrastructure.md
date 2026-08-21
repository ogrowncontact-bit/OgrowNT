# Universal Broker & Exchange Connectivity + Execution Infrastructure ("PROMPT 13")

## The central constraint

> EXECUTION MUST BE BLOCKED for anything but paper. Mesmo que credenciais
> de produção existam: EXECUTION MUST BE BLOCKED.

Nothing in this phase makes live trading reachable — it makes the paper
execution path a genuinely broker-shaped one, so that the *only* thing a
future, explicitly-approved live-trading phase would need to change is one
new adapter registration, never the pipeline around it. The second
constraint that shapes every module below:

> se broker retornar estado desconhecido: UNKNOWN. Nunca assumir FILLED.

An order whose true outcome isn't known is persisted as `status="unknown"`,
never coerced into a false positive or a false negative — see
`tests/test_execution_chaos.py::test_unknown_order_status_is_never_silently_treated_as_filled`
and Scenario B in `tests/test_broker_e2e_scenarios.py`.

## Why this phase is mostly a thin new layer

Nearly every mechanism "PROMPT 13" asks for already existed from earlier
phases. This pass's job was almost entirely *widening an existing interface
into a broker-shaped one* and *wiring one new gate*, not execution logic
from scratch:

| Prompt 13 asks for | Reuses |
|---|---|
| Universal broker interface | `packages/execution/adapters/base.py::ExecutionProvider` (Phase 3) — `BrokerAdapter` is a strict structural superset |
| Paper execution | `PaperExecutionProvider` (Phase 3/6) — `PaperBrokerAdapter` extends it, never replaces it |
| Order idempotency | `order_manager.py`'s `_idempotency_key` (Prompt 8), unchanged |
| Account/cash reconciliation | `packages/portfolio/reconciliation.py::PaperReconciliationEngine` (Prompt 8), unchanged — broker reconciliation is layered ON TOP |
| Market session status | `packages/market/sessions.py::MarketSessionEngine` (Prompt 11) |
| Net execution expectancy | `packages/risk/costs.py::evaluate_net_expectancy` (Prompt 12), left deliberately unwired pending exactly this module |
| Transaction cost model | `packages/execution/fills.py::simulate_fill` (Phase 3/6), the same model the Backtest Engine uses |
| "architecture-ready, tested via stubs since only one real implementation exists" | `packages/data/connectors/market/failover.py` (Prompt 12)'s own precedent, reused for `BrokerRegistry`/`ExecutionRouter`/`RateLimitManager`/`ClockService`/`SymbolMapper` |
| AST-walk structural red-team proofs | `tests/test_capital_defense_red_team.py` (Prompt 12), `tests/test_research_red_team.py` (Prompt 10) |

The genuinely new work is: the `BrokerAdapter` Protocol and its
`PaperBrokerAdapter`/`LiveBrokerAdapter` implementations, the
`LiveTradingFirewall`, the `ExecutionGate`, instrument precision, fee
engine, execution quality, broker health, rate limiting, retry policy,
clock sync, symbol mapping, the execution router, broker-level
reconciliation, the credential-isolation abstraction, and the order
lifecycle's genuinely new fill states (`partially_filled`, `unknown`) — plus
the worker cadences, API routers, and dashboard panel that make all of it
observable. Seven new tables (not the spec's literal ~14) and a handful of
column extensions on `Asset`/`Order`/`TradingEvent` — deliberately not a new
schema subsystem.

## Module map

```
packages/execution/
├── adapters/base.py       (MODIFIED — OrderType/OrderStatus widened additively)
├── broker/
│   ├── base.py            BrokerAdapter Protocol (@runtime_checkable) + AccountInfo/PositionInfo/HealthCheckResult
│   ├── capabilities.py     BrokerCapabilities + PAPER_CAPABILITIES
│   ├── registry.py         BrokerRegistry + build_default_registry + get_or_create_broker_row
│   ├── paper.py            PaperBrokerAdapter — the ONLY adapter this codebase's own processes construct
│   └── live.py             LiveBrokerAdapter — self-destructs on __init__ and on every attribute access
├── firewall.py             LiveTradingFirewall + ENABLE_LIVE_TRADING (hardcoded False, tripwire-guarded)
├── gate.py                 ExecutionGate — final revalidation immediately before order_manager
├── instrument.py           InstrumentSpec + validate_precision
├── fee_model.py            FeeModel + PROVIDER_FEE_RATES + FEE_KINDS + default_fee_model() (relocated from packages/backtest)
├── fees.py                 FeeEngine
├── quality.py              assess_execution_quality — read-side aggregation over Order/Execution
├── health.py               assess_broker_health — HEALTHY/DEGRADED/UNAVAILABLE/QUARANTINED
├── rate_limit.py           RateLimitManager — token bucket per (broker, category)
├── retry.py                RetryPolicy + RETRYABLE_OPERATIONS allowlist
├── clock.py                ClockService — drift detection
├── symbol_mapper.py        SymbolMapper — canonical <-> provider symbol
├── router.py                ExecutionRouter + OrderTypeSelector
├── broker_reconciliation.py Broker-level reconciliation, layered on top of the Prompt-8 cash engine
├── broker_events.py         Idempotent broker event dedup (SHA-256 payload hash)
└── secrets.py                SecretProvider + EnvSecretProvider + mask()

apps/worker/broker_health.py, order_monitor.py, broker_reconciliation.py  (3 new cadences)
apps/api/routers/brokers.py, execution.py                                (2 new routers)
apps/dashboard/components/ExecutionCommandCenter.tsx                     (1 new panel)
```

## BrokerAdapter: a structural superset, not a rewrite

`packages/execution/broker/base.py::BrokerAdapter` is a `Protocol`, marked
`@runtime_checkable` specifically so `apps/worker/risk_execution.py` can
narrow a plain `ExecutionProvider` to the richer type with `isinstance()`
rather than a fragile `hasattr()` check. Every method
`ExecutionProvider` already defines (`submit_order`/`cancel_order`/
`get_order`/`get_balance`) keeps its exact signature — `order_manager.py`,
the sole writer of `Position`/`Trade` rows, is completely untouched.
`BrokerAdapter` adds account/position/order-history introspection, market
data pass-through, connection lifecycle, and fee/instrument/capability
lookups: the richer surface a real broker integration needs that a single
synchronous `submit_order()` call never did.

`PaperBrokerAdapter(PaperExecutionProvider)` is the only adapter this
codebase's own `apps/worker`/`apps/api` processes ever construct. Two
genuinely new fill behaviors beyond what `PaperExecutionProvider` already
did:

- **Volume-capped partial fills.** `PARTIAL_FILL_VOLUME_THRESHOLD = 3.0`:
  a requested quantity above 3× the bar's own volume fills only the
  portion the market could plausibly absorb in one tick
  (`status="partially_filled"`); the remainder is simply not filled — no
  fabricated resting order. `order_manager.py::open_position()` sizes the
  resulting `Position` at the quantity that *actually* filled
  (`result.detail["filled_qty"]`), never the originally requested
  quantity.
- **Marketable-limit orders.** A limit order whose price already crosses
  the current market fills immediately, capped so it never fills worse
  than the limit — exactly what a real limit order guarantees. A
  NON-marketable limit order (one that would need to rest and wait) is
  honestly **rejected** with `reason="limit_queuing_not_implemented"`
  rather than fabricating a queued/resting-order state nothing in this
  synchronous, single-tick paper broker would ever come back to resolve.

`LiveBrokerAdapter` (`packages/execution/broker/live.py`) exists only so the
shape is ready. It is never a usable implementation: `__init__` raises
`LiveTradingDisabledError` immediately, and `__getattr__` raises the same
error for any method access that somehow got past construction. No network
client, no credential handling, no order construction logic exists in that
file — nothing a future "enable live trading" change could accidentally
activate by flipping one flag.

## Defense in depth: four independent layers keep live trading unreachable

`packages/execution/firewall.py`'s own docstring documents three layers by
design (no single point of failure); the end-to-end test suite surfaced a
fourth, already-existing one from Prompt 8:

1. **`SystemState.trading_mode`'s DB `CHECK` constraint.** `'live'` has
   never been a legal value — even a direct `UPDATE system_state SET
   trading_mode='live'` is rejected by Postgres itself
   (`tests/test_execution_red_team.py`#6).
2. **`packages/risk/engine.py`'s step 1c** (present since Prompt 8, §2-4 of
   that phase's own spec) — `evaluate_signal()` refuses anything but
   `trading_mode in (None, "paper")` before a signal ever reaches the
   Portfolio Manager or the `ExecutionGate` at all. This is what actually
   catches a hypothetical `trading_mode="live"` `SystemState` first in
   practice — proven by `tests/test_broker_e2e_scenarios.py`'s Scenario E,
   which discovered this ordering (the initial expectation was that the
   `ExecutionGate` would be the first thing to catch it; it turned out
   Prompt 8's own Risk Engine already does, one layer earlier).
3. **`packages/execution/firewall.py`'s `LiveTradingFirewall` +
   `ENABLE_LIVE_TRADING: Final[bool] = False`.** Hardcoded, never read from
   settings/env/DB/a config file — no mutation path exists anywhere in this
   codebase for any caller to change it at runtime. A self-check tripwire
   raises `RuntimeError` at import time if it were ever flipped `True`,
   forcing a deliberate code review rather than a silent activation.
   `LiveTradingFirewall.check()` is called from `ExecutionGate` (every
   order, before it reaches `order_manager`) and from `ExecutionRouter`
   (broker selection never even considers a `'live'`-kind adapter).
4. **`packages/execution/broker/live.py::LiveBrokerAdapter`.** Self-destructs
   on `__init__` and on any attribute access — even a caller that bypassed
   every layer above and somehow obtained a live adapter instance can't use
   it.

The §27 TWO-KEY SAFETY concept (`SYSTEM_ENABLE` + `USER_ENABLE`) is
deliberately **not** implemented as a working unlock mechanism this phase —
building a real two-key unlock now would be building the very door this
phase is required to keep welded shut.

## ExecutionGate: the final revalidation

`packages/execution/gate.py::evaluate()` is inserted into
`apps/worker/risk_execution.py::maybe_execute()` between Portfolio Manager
approval and `order_manager.open_position()`. Risk Engine and Portfolio
Manager approval already happened by this point, but that approval can be
seconds to minutes stale by the time a real submit actually happens — this
module re-checks the handful of things that could have genuinely changed in
that window, plus two checks nothing upstream performs at all:

```
LiveTradingFirewall (unconditional, first)
        │
        ▼
signal expiration ──► quantity > 0 ──► market session open
        │
        ▼
broker health (when a BrokerAdapter is supplied)
        │
        ▼
data availability (real OHLCV, data_quality == "high")
        │
        ▼
price deviation (|current - entry| / entry <= MAX_PRICE_DEVIATION_PCT)
        │
        ▼
instrument precision (tick/step/min quantity/min notional)
        │
        ▼
net expectancy (packages/risk/costs.py::evaluate_net_expectancy —
                 built in Prompt 12, wired here for the first time)
        │
        ▼
ExecutionApproval(approved=True, expires_at=now + 30s)
```

`MAX_PRICE_DEVIATION_PCT = 1.0` is a fixed engineering constant, not a
`risk_limits.yaml`-tunable number: it's a sanity bound on "did the price
move enough since the signal was scored that resubmitting blind would be a
mistake," not a portfolio-level risk limit. `ExecutionApproval` is a plain
dataclass, never a persisted table — see the schema section below for why.

## Order lifecycle: partial fills and Execution rows

`order_manager.py::open_position()` now honestly handles a
`partially_filled` `OrderResult` — the original `PaperExecutionProvider`
never returned this status, so every pre-existing caller/test is
unaffected. The `Position` is sized at `result.detail["filled_qty"]`
(falling back to the requested quantity when a provider doesn't supply it),
never either rejecting the whole order or silently pretending the full size
filled.

A new `Execution` row is created on every real fill — one row **per fill
event**, never per order (§40's "nunca assumir one order = one fill"). A
rejected order produces zero `Execution` rows.
`close_position()`/`reduce_position()` gained the same `Execution`-row
creation for their existing full-fill path, but deliberately **not** the
same partial-fill handling `open_position()` got: a closing/reducing order
is essentially always much smaller than the position's own original
opening order, so it practically never trips `PaperBrokerAdapter`'s
volume-based partial-fill threshold in practice, and building full
partial-close semantics (a position simultaneously mid-close and still
partially open) would be a meaningfully bigger change than this phase's
scope calls for. A partial fill on close/reduce is treated the same
conservative way a full rejection already was: nothing changes, the Trade
Monitor retries next cycle.

## Broker health and reconciliation

`packages/execution/health.py::assess_broker_health` follows the same
"current call plus persisted trend" pattern as
`packages/shared/worker_health.py`: a single `health_check()` call decides
`HEALTHY`/`DEGRADED` by latency, and a run of consecutive failed checks
(read back from the new `broker_health_checks` table) is what promotes
`UNAVAILABLE` to `QUARANTINED` — one failure is noise, a streak is a
signal.

`packages/execution/broker_reconciliation.py` is layered **on top of**,
never a replacement for, the existing cash-only `PaperReconciliationEngine`
(Prompt 8, unchanged): that one reconstructs cash from first principles
every tick and already pauses trading on a mismatch. This module
additionally compares what a `BrokerAdapter` **reports**
(`get_account()`/`get_positions()`/`get_open_orders()`) against this
system's own internal ledger. On mismatch it pauses via
`SystemState.trading_paused` — **never** the Kill Switch, the same
deliberate distinction the cash-reconciliation engine already documents for
itself: this is an accounting-integrity stop, not a market-risk stop.

**Honesty note:** `PaperBrokerAdapter`'s own `get_account()`/
`get_positions()`/`get_open_orders()` are derived from the *same*
`positions`/`orders` tables this module compares them against — so in this
deployment, this check will by construction never find a real divergence.
That is not a limitation worth hiding: it's the same honest
"architecture-ready, proven via synthetic injection since only one real
implementation exists" situation as
`packages/data/connectors/market/failover.py` (Prompt 12). Tests exercise
the mismatch-detection path with a stub adapter that deliberately reports
different numbers, not by hoping `PaperBrokerAdapter` someday disagrees
with itself — and `tests/test_broker_e2e_scenarios.py`'s Scenario C proves
the mismatch propagates all the way to a real subsequent signal actually
being blocked, not just to a standalone reconciliation-layer assertion.

## Idempotent broker events

`packages/execution/broker_events.py::record_event()` hashes the event
payload with SHA-256 and enforces a `(broker_id, event_type, payload_hash)`
unique constraint — a duplicate or out-of-order-arriving event is a no-op,
never processed twice (§101-103). The `broker_health` worker cadence keys
its payload on `state` alone (excluding the noisier `latency_ms`), so
consecutive identical health states genuinely dedupe rather than always
producing a "different" payload by construction.

## Circular-import fix: fee_model.py relocation

`FeeModel`/`PROVIDER_FEE_RATES`/`FEE_KINDS`/`default_fee_model()` were
physically moved from `packages/backtest/execution_models.py` to a new
`packages/execution/fee_model.py`. `packages/execution` is a lower-level,
shared package that must never import FROM `packages/backtest` — that
dependency already runs the other direction (`packages/backtest` imports
FROM `packages/execution/fills.py`), and `apps/worker` must never
transitively import `packages/backtest` at all. `execution_models.py` now
re-exports the same names under `__all__`, so all 5 pre-existing consumers
keep working byte-for-byte unchanged.

## Rate limiting, retry, clock, symbol mapping: architecture-ready, honestly untested against a real second source

`RateLimitManager`, `RetryPolicy`, `ClockService`, and `SymbolMapper` are
all genuine, working implementations — a real token bucket, a real
exponential backoff, real drift detection, a real bidirectional symbol
table — but none of them is exercised against a real second broker or
provider, because none exists in this deployment. `PaperBrokerAdapter`
makes no network calls at all, so nothing in this codebase's own
worker/API processes can ever actually approach a rate limit, retry a
failed network call, or observe real clock drift. This is the same
"built for real, tested via synthetic exhaustion/stubs since only one
honest implementation exists" precedent as
`packages/data/connectors/market/failover.py` (Prompt 12).

`RETRYABLE_OPERATIONS` is the safety mechanism, not a suggestion: it is an
allowlist of read-only, side-effect-free operations
(`health_check`/`get_account`/`get_positions`/...). `create_order`/
`submit_order`/`cancel_order`/`replace_order` are structurally absent —
`retry_with_backoff()` raises a hard `ValueError` for any operation
`is_retryable()` doesn't approve, rather than silently retrying an order
submission whose response may have simply gotten lost (§53-54's "nunca
repetir cegamente: order submission... primeiro: query order status").

## ExecutionRouter: never fee alone

`packages/execution/router.py::ExecutionRouter` hard pre-filters (never a
`kind=="live"` adapter; capability match against the requested order
type/asset class; a live health check) before scoring survivors on a
blended fee(0.6)+latency(0.4) composite. §69's "não escolher broker
simplesmente porque fee = lowest" is enforced structurally: a broker can
never win purely on the cheapest fee if a healthy competitor is
meaningfully faster — proven by `tests/test_execution_red_team.py`#9, which
confirms a `'live'`-kind adapter registered as the explicit default is
still never selected.

## Credential isolation

`packages/execution/secrets.py::SecretProvider`/`EnvSecretProvider` reads
only from process environment variables — never a database column, never
logged, never placed in an LLM prompt or returned to the frontend. Only a
`BrokerAdapter`'s own `__init__`/`connect()` may ever call
`SecretProvider.get()` — enforced today by the simple fact that
`PaperBrokerAdapter` never calls this module at all (it needs no
credentials), and structurally proven by
`tests/test_execution_red_team.py`'s AST walk confirming no agent/
strategy/research/LLM module imports `packages.execution.secrets`.
`mask()` never returns the raw value, for anywhere that needs to show a
credential exists without exposing it.

## Why 7 tables, not ~14

`BrokerCapability`, `Instrument`, `ExecutionRequest`, `ExecutionApproval`,
`BrokerCredentialReference`, and `Fee` are all runtime dataclasses
(`packages/execution/broker/capabilities.py`, `instrument.py`, `gate.py`,
`secrets.py`, `fees.py`) computed fresh from a broker adapter call or from
`Asset`'s own new precision columns, never persisted. A persisted row for
any of them would either always mirror the same adapter call
(`BrokerCapability`, `Instrument`) or always mirror data another table
already owns in full — `ExecutionRequest`/`ExecutionApproval`'s audit trail
*is* the `Order` row itself plus its `decision_id`/`risk_decision_id` FKs; a
`Fee` is just `Execution.fee`. The 7 tables that genuinely earned a schema
row: `Broker`, `BrokerHealthCheck`, `AccountSnapshot`,
`BrokerPositionSnapshot`, `Execution`, `BrokerEvent`, `ReconciliationRun`.

## API and dashboard

New under `apps/api/routers/brokers.py`: `GET /api/brokers`,
`GET /api/brokers/{id}`, `GET /api/brokers/{id}/health`. New under
`apps/api/routers/execution.py`: `GET /api/accounts`,
`GET /api/orders/{id}`, `GET /api/executions`, `GET /api/reconciliation`,
`GET /api/instruments[/{symbol}]`, `GET /api/execution/health` — all
admin-only, same `get_current_admin` dependency every other admin-only
router already uses.

`ExecutionCommandCenter.tsx` shows registered brokers and their health,
broker-reported accounts/positions, recent orders and executions,
reconciliation run history, and the execution quality summary — reading
from the same real tables the rest of the dashboard does, never a second,
parallel data source (proven by
`tests/test_execution_broker_api.py::test_asset_with_real_ohlcv_shows_up_in_accounts_and_instruments`).

## Deliberate divergences

1. **7 new tables, not the spec's literal ~14** — see above.
2. **Partial fills only for MARKET orders.** A resting/queued LIMIT order is
   honestly rejected rather than fabricated, since this synchronous,
   single-tick paper broker has no order book / matching engine.
3. **`FeeModel` relocated from `packages/backtest` to
   `packages/execution/fee_model.py`** to avoid a circular package
   dependency — a genuine architectural fix, not a cosmetic move.
4. **`MAX_PRICE_DEVIATION_PCT` is a fixed constant, not
   `risk_limits.yaml`-configurable** — an engineering sanity bound on
   resubmission staleness, not a portfolio risk limit.
5. **Broker-level reconciliation is "clean by construction" in this
   deployment** — `PaperBrokerAdapter`'s own view is derived from the same
   tables it's compared against; proven via synthetic stub-adapter
   mismatches instead.
6. **No real second broker exists to test failover/routing against** — same
   honest scoping as Prompt 12's `FailoverMarketDataProvider`.
   `RateLimitManager`/`ClockService`/`SymbolMapper` are all
   architecture-ready but not exercised by a real second source, for the
   same reason.
7. **The §27 TWO-KEY SAFETY concept is not a working unlock mechanism this
   phase** — live stays blocked regardless of any key's state.
8. **`close_position()`/`reduce_position()` don't get the same partial-fill
   handling `open_position()` does** — a closing/reducing order practically
   never trips the volume-based partial-fill threshold in the first place;
   building full partial-close semantics was judged out of this phase's
   scope.
9. **A fourth live-trading defense layer was discovered, not designed, this
   phase**: `packages/risk/engine.py`'s Prompt-8-era `trading_mode` check
   catches a hypothetical live attempt one layer before the `ExecutionGate`
   even runs — found while writing `tests/test_broker_e2e_scenarios.py`'s
   Scenario E, whose original assertion (`gate_rejected`) had to be
   corrected to what the system actually, correctly does (`risk_rejected`).

## Testing

159 new tests across `test_broker_adapter.py` (22), `test_broker_registry.py`
(7), `test_live_trading_firewall.py` (8), `test_execution_gate.py` (11),
`test_broker_health.py` (5), `test_broker_reconciliation.py` (8),
`test_execution_router.py` (7), `test_instrument_precision.py` (8),
`test_fee_engine.py` (6), `test_execution_quality.py` (5),
`test_rate_limit_manager.py` (5), `test_retry_policy.py` (6),
`test_clock_service.py` (5), `test_symbol_mapper.py` (3),
`test_broker_event_store.py` (4), `test_order_lifecycle.py` (5),
`test_execution_broker_api.py` (12), `test_execution_red_team.py` (20-item
AST-walk + behavioral battery), `test_execution_chaos.py` (7 chaos
scenarios), and `test_broker_e2e_scenarios.py` (5 full end-to-end
scenarios: paper pipeline executed + reconciled clean; broker network
failure → UNKNOWN → safe continuation; reconciliation mismatch → a real
subsequent signal blocked; a full real 18-agent cycle never creates an
Order/Position; live-trading attempt blocked at the full pipeline level).
1401/1401 in the full suite.
