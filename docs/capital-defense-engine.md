# Advanced Risk & Capital Defense Engine ("PROMPT 12")

## The central constraint

> RiskScore NÃO representa probabilidade de perda. É um indicador composto
> de condições de risco.

Every number this package reports is a *composite severity indicator*, not
a forecast — same discipline as the existing `OpportunityScore`
(`docs/blueprint/`'s Phase 2/3 scoring engine) and
`packages/quant/learning/strategy_stats.py`'s `health_score`. Nothing in
this package predicts P&L; it aggregates already-computed evidence into one
number and one state.

The second constraint that shapes the whole aggregation model:

> Se o sistema não sabe se é seguro: NÃO operar.

Every dimension below fails **closed**: if a computation raises, that
dimension's contribution is `HALTED`, `AdvancedRiskAssessment.degraded` is
set `True`, and the failure is recorded in `reasons` — never silently
skipped, never defaulted to "safe."

## Why this phase is mostly a thin new layer

Nearly every mechanism "PROMPT 12" asks for already existed from earlier
phases. This pass's job was almost entirely *aggregation and orchestration*
on top of proven primitives, not new risk logic from scratch:

| Prompt 12 asks for | Reuses |
|---|---|
| Drawdown response ladder | `PortfolioState.drawdown_pct` (Phase 3) + new config-driven thresholds |
| Loss-streak dimensions | `packages/risk/loss_streak.py` (Phase 8), extended additively |
| Concentration / hidden factors | `packages/market/clustering.py::find_clusters` (Prompt 11), repointed at open positions |
| Transaction cost model | `packages/execution/fills.py::simulate_fill` (Phase 3/6), the same model `PaperExecutionProvider` and the Backtest Engine use |
| Live stress testing | `packages/backtest/monte_carlo.py` + `risk_of_ruin.py` (Prompt 7), run against real `Trade` history instead of a backtest's |
| System risk | `packages/shared/worker_health.py` heartbeat/cadence machinery (Prompt 8) |
| Model risk | `Decision.contradiction_score` / `critical_agent_failure`, already computed every cycle by `packages/agents/chief.py` (Prompt 9) |
| Data risk | `Asset.data_quality_score`, already refreshed every universe cycle (Prompt 11) |
| System/portfolio circuit breakers | Kill Switch (`SystemState.trading_enabled`) and Safety Belt EMERGENCY/KILL_SWITCH (Phase 3/Prompt 4) |
| Strategy/asset circuit breakers | Strategy Quarantine (Phase 5) and Asset quarantine (Prompt 11) |

The genuinely new work is: the config-driven drawdown ladder, the
concentration/execution/data risk dimensions, the 7-level `RiskState`
aggregator, the `EmergencyKillSwitch` 4-state machine, the risk-config
audit trail, and a `FailoverMarketDataProvider` — plus the worker cadence
and dashboard panel that make all of it observable and actionable. Two new
tables (`risk_config_versions`, `risk_assessments`) and a handful of column
extensions on `SystemState`/`RiskDecision` — deliberately not a new schema
subsystem.

## RiskState: a second, independent composite

`packages/risk/capital_state.py` defines a **new** 7-level vocabulary —
`NORMAL → CAUTION → DEFENSIVE → HIGH_RISK → CRITICAL → EMERGENCY → HALTED`
— that sits **alongside**, not on top of, the existing 5-level Safety Belt
(`packages/risk/safety_belt.py`, Prompt 4: `normal/caution/defensive/
emergency/kill_switch`). The two are computed independently and can
diverge: a correlation spike can push `RiskState` to `HIGH_RISK` while
drawdown — and therefore the Safety Belt — is still `NORMAL`. Neither
replaces the other; `evaluate_signal()` reads both.

Aggregation across the 7 dimensions is a **`max()`** over the ordered
`RISK_STATES` tuple — never an average — enforcing §9's "nenhum nível
inferior pode substituir um nível superior" structurally rather than by
convention. `HALTED` is reachable **only** through a tripped system or
portfolio circuit breaker: the drawdown ladder tops out at `EMERGENCY`
(`_LEVEL_RISK_STATES` in `capital_state.py` has 5 entries, one per DD
level, and none of them is `HALTED`), and an execution/data breaker alone
caps the aggregate at `EMERGENCY` too (`advanced_engine.py`'s
`breaker_override` logic). This is proven both structurally (the tuple
itself has no path to `HALTED` outside the breaker-override branch) and by
a dedicated test
(`test_execution_breaker_alone_forces_emergency_not_halted`).

## The drawdown ladder

`config/risk_limits.yaml`'s `drawdown_levels` section defines `level_1`
through `level_5`, each a `threshold_pct` + a `response` string.
`load_risk_limits()` rejects a non-strictly-increasing ladder at load time
— the same fail-fast discipline the rest of `packages/risk/config.py`
already applies to other limit blocks. `level_5` (15%) deliberately
coincides with the pre-existing `max_portfolio_drawdown_pct` hard block,
so the ladder's most severe rung lines up with the circuit that already
stops trading outright.

Levels map onto `RiskState` one-to-one (`level_1→CAUTION`, ...,
`level_5→EMERGENCY`). `assess_drawdown()` applies a **recovery cooldown**
(`recovery.cooldown_minutes`, default 60): the *effective* drawdown used
for classification is the maximum of the instantaneous value and the
actual peak drawdown recorded in `portfolio_snapshots` over the trailing
cooldown window. This is deliberately **stateless** — computed on demand
from existing snapshot history, the same technique
`packages/portfolio/state.py` already uses for its weekly/monthly lookback
windows — rather than a new persisted "level breached at" timestamp. A
level can only de-escalate once the real trailing max, not just the
current instant, has genuinely fallen below it, which is what makes it a
hysteresis rather than a raw threshold check.

## Circuit breakers and the Emergency Kill Switch

Six named breakers (`packages/risk/circuit_breakers.py`), four of which
report on an existing mechanism rather than adding a new one:

| Breaker | Trips on |
|---|---|
| `system` | Kill Switch (`SystemState.trading_enabled == False`) |
| `portfolio` | Safety Belt at `EMERGENCY`/`KILL_SWITCH` |
| `strategy` | `StrategyRow.lifecycle_stage == "quarantine"` |
| `asset` | `Asset.status == "quarantined"` |
| `execution` | `ExecutionRiskAssessment.state == CRITICAL` (genuinely new) |
| `data` | `DataRiskAssessment.state == CRITICAL` (genuinely new) |

`EmergencyKillSwitch` layers a 4-state machine — `ARMED → TRIGGERED →
LOCKED → RECOVERY` — onto the **same** `SystemState.trading_enabled`
boolean every other kill-switch-aware module already reads; it is not a
second, competing on/off switch. `TRIGGERED` is transient and never
persisted on its own (a trip goes straight `ARMED → LOCKED`).
`start_recovery()`/`confirm_recovery()` both require an explicit `actor`
string — RBAC enforcement (only an admin can call them) is the API layer's
job via `require_admin_role`, the same pattern every other admin-only
mutation in this codebase already follows.
`confirm_recovery()` requires `check_recovery_readiness()` — which reuses
the System Risk Engine's own heartbeat/cadence-failure signal rather than
a second health check — to report ready, unless `force=True`, itself
recorded in the resulting `AuditLog` row as `forced: true`.

No AI, agent, strategy, or research code path in this repository calls
`trigger_kill_switch`, `start_recovery`, or `confirm_recovery`, or assigns
`trading_enabled`/`kill_switch_state` directly — enforced by an AST-walk
red-team battery (`tests/test_capital_defense_red_team.py`), the same
technique already used for the agent and research sandboxes.

## The Advanced Risk Engine: RiskScore and RiskState

`packages/risk/advanced_engine.py::assess_portfolio_risk()` computes seven
dimensions — drawdown, concentration, loss streak, system, execution,
model, data — each independently, each fail-closed, then combines them:

```
capital/drawdown ──┐
concentration ──────┤
loss streak ────────┤
system risk ────────┼──► max() over RISK_STATES ──► risk_state
execution risk ──────┤         ▲
model risk ──────────┤         │ (or forced HALTED/EMERGENCY by a
data risk ───────────┘         │  tripped circuit breaker)
                                │
circuit breakers ───────────────┘

weighted blend (Σ weight_i × severity_i, weights sum to 1.0) ──► risk_score
  (floored at the breaker's own severity ONLY when a breaker tripped)
```

`risk_score` is a fixed-weight blend (drawdown 0.30, concentration 0.15,
system 0.15, execution 0.10, model 0.10, data 0.10, loss_streak 0.10 — sums
to 1.0, same "documented assumption, not a fitted model" convention as
`strategy_stats.py`'s own `_HEALTH_WEIGHTS`).

### The RiskScore floor bug, found and fixed mid-phase

The first implementation floored `risk_score` at `severity(risk_state)`
unconditionally: `risk_score = max(weighted_score, severity(risk_state))`.
This is mathematically dead code. Since the seven weights sum to exactly
1.0, and every individual dimension's severity is, by construction, `<=`
the maximum dimension's own severity (`risk_state` **is** that maximum),
`weighted_score` can never exceed `severity(risk_state)` — the `max()`
always resolves to the floor. `risk_score` was silently *always* equal to
`severity(risk_state)`, never a genuine composite of all seven dimensions,
contradicting §9's own "RiskScore é um indicador composto."

This was caught by an end-to-end scenario test that stacked several
dimensions at once and asserted the blend should sit strictly below any
single dimension's own severity (`test_capital_defense_e2e_scenarios.py`
Scenario D) — a case the earlier hand-picked unit tests hadn't covered. The
fix applies the floor **only** when a circuit breaker actually tripped
(`breaker_override is not None`): a tripped breaker is a discrete,
structural severity a smooth 7-dimension blend could otherwise understate
(e.g. a kill switch tripped for a reason none of the seven dimensions
individually reflect), so that path still floors at the breaker's own
severity. Absent a breaker trip, `risk_score = round(weighted_score, 2)`
directly — restoring genuine aggregation for the ordinary escalation path.
Three tests in `tests/test_advanced_risk_engine.py` pin this down:
`test_risk_score_is_zero_when_every_dimension_is_normal`,
`test_risk_score_is_a_genuine_weighted_blend_not_a_mirror_of_risk_state`,
and `test_risk_score_is_floored_at_the_breakers_own_severity_when_one_trips`.

`capital_preservation_mode` and `zero_trade_mode` are pure functions of the
final `risk_state` (`>= HIGH_RISK` and `>= CRITICAL` respectively), never a
separately-drifting computation.

## Wiring into the trading loop

`AdvancedRiskAssessment` is computed **once per worker cycle**
(`apps/worker/strategy_runner.py::run_strategy_cycle`), not once per
signal — unlike `portfolio_state`, which genuinely does change signal to
signal as positions open mid-cycle, a portfolio-wide risk snapshot doesn't
meaningfully move between individual signal evaluations within the same
cycle. It flows into `packages/risk/engine.py::evaluate_signal()` as a new,
fully optional `advanced_risk` parameter — every pre-existing caller
(including the Critical Safety Battery's direct calls) is unaffected when
it's omitted (`None`, the default).

When present, it adds one more step to the sovereign 13-step decision
pipeline:
- `zero_trade_mode` → hard block, no exceptions.
- `capital_preservation_mode` → requires at least `high_quality` tier
  (`tier_meets_floor`); anything below is blocked regardless of score.
- Otherwise, a size multiplier is applied at `CAUTION`/`DEFENSIVE`
  `RiskState`, reusing the **same** `safety_belt_multipliers.caution`/
  `.defensive` values from `config/risk_limits.yaml` the Safety Belt
  already uses — deliberately not a second, independent multiplier table.

A new, independently-cadenced worker function,
`apps/worker/capital_defense.py::run_capital_defense_cycle` (default 120s,
`capital_defense_interval_seconds`), persists a `RiskAssessment` row on
**every** tick regardless of signal activity — the durable history
`GET /api/risk/advanced` (computed fresh, not read from this table) doesn't
provide on its own — and syncs `SystemState.capital_preservation_mode`/
`zero_trade_mode`. It raises an `Alert` only on a **fresh** transition into
or out of `HIGH_RISK`+ (compared via a `was_elevated`/`is_elevated`
boolean, not a stored "previous state" column), so an already-elevated
portfolio doesn't spam an alert every 120 seconds.

## API and dashboard

`GET /api/risk` (existing, Prompt 4) gained `drawdown_levels`/`recovery` in
its `limits` payload. New under the same `/api/risk` prefix:
`GET /advanced`, `GET /breakers` (optional `strategy_id`/`asset_id`),
`GET /concentration`, `GET /stress` (Monte Carlo/Risk-of-Ruin + VaR/CVaR
together, always both — §84's "never the sole metric"),
`GET /kill-switch/state`, `POST /kill-switch/recovery/start` (admin),
`GET /kill-switch/recovery/readiness`,
`POST /kill-switch/recovery/confirm` (admin, `force` param),
`GET /config-versions`, `GET /config-versions/{version}`,
`GET /config-versions/diff/{from_version}/{to_version}`. The existing
`PATCH /api/system/risk-limits` (Prompt 4) now also calls
`record_config_version()` after writing `config/risk_limits.yaml`, so every
live limit change is versioned and attributed to the admin who made it.

The dashboard's `CapitalDefenseCenter.tsx` panel shows the RiskState badge,
a Risk Score / Drawdown / Capital Preservation / Zero Trade Mode card grid,
the per-dimension sub-state row, `reasons`, a degraded warning when
`degraded=True`, the six circuit breakers, a concentration summary, and the
Emergency Kill Switch box with a `RecoveryButton` that walks
LOCKED → RECOVERY → ARMED through the two admin-only endpoints above.

## Deliberate divergences

1. **`RiskState` is a new, separate composite from the Safety Belt.** The
   spec's vocabulary overlaps in name (`CAUTION`, `DEFENSIVE`) but the two
   engines are computed independently and can disagree — reusing the Safety
   Belt's own 5-state field for this would have collapsed two genuinely
   different signals into one.
2. **`HALTED` is reachable only via a tripped system/portfolio circuit
   breaker.** The drawdown ladder and the systemic-risk dimensions
   deliberately cap at `EMERGENCY` — full system stop is reserved for a
   discrete circuit-breaker event, not an emergent property of stacking
   enough "merely severe" dimensions.
3. **RiskScore floors at the breaker's severity only when a breaker
   tripped** (see above) — a mid-phase correction to the original spec
   reading, made because the literal "always floor at severity(risk_state)"
   interpretation makes the weighted blend mathematically unreachable.
4. **No margin mechanics.** `CapitalState.margin_used` is always `0.0` —
   this is still a cash-only paper-trading account (same "PROMPT 8" §41
   precedent as `leverage.max_leverage`).
5. **`FailoverMarketDataProvider` is architecture-ready but untested
   against a real second live provider.** This codebase has exactly one
   real provider implementation (`MockMarketDataProvider`); tests exercise
   the failover/cross-check logic with two independent stub providers
   instead of fabricating a second "real" source.
6. **`liquidity_state`/`event_state`/`volatility_state` on `RiskDecision`
   stay `NULL`.** The migration reserved these columns for potential future
   dimensions; this phase's seven dimensions (drawdown, concentration, loss
   streak, system, execution, model, data) don't map onto them, and writing
   a fabricated value would violate this project's "no hallucinated data"
   rule.
7. **VaR/CVaR use historical simulation, not a parametric model.**
   `compute_value_at_risk()` sorts real `portfolio_snapshots` equity
   returns rather than assuming a normal distribution — consistent with
   this codebase's existing preference (Monte Carlo, walk-forward) for
   resampling real data over fitting a distributional assumption.

## Testing

158 new tests across `tests/test_capital_state.py`,
`tests/test_risk_loss_streak.py` (extended), `tests/test_concentration.py`,
`tests/test_transaction_costs.py`, `tests/test_risk_stress.py`,
`tests/test_systemic_risk.py`, `tests/test_circuit_breakers.py`,
`tests/test_advanced_risk_engine.py`, `tests/test_risk_config_version.py`,
`tests/test_market_data_failover.py`, `tests/test_capital_defense_cadence.py`,
`tests/test_advanced_risk_api.py`, `tests/test_capital_defense_red_team.py`
(14-item AST-walk + behavioral battery), and
`tests/test_capital_defense_e2e_scenarios.py` (4 full scenarios: deep
drawdown → block → cooldown-gated recovery; kill-switch trip → HALTED →
admin-driven recovery → NORMAL; execution-only degradation capping at
EMERGENCY with an open position left untouched; multi-dimension stacking —
the scenario that surfaced the RiskScore floor bug above). 1242/1242 in the
full suite.
