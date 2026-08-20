# Multi-Agent Quant Intelligence Architecture ("PROMPT 9")

## The 18 agents

`packages/agents/specialists/__init__.py::SPECIALIST_REGISTRY` is the
single source of truth — code, display name, and whether it casts a real
directional vote.

| Agent | Directional | Wraps |
|---|:---:|---|
| Chief Quant | yes | regime-weighted `calculate_expected_value()` across `ALL_STRATEGIES` |
| Technical Analysis | yes | `IndicatorSet` confirmation-count vote (SMA cross/RSI zone/trend sign) |
| Pattern Hunter | yes | `packages/quant/patterns/detector.py::detect_all` |
| Market Regime | yes | `MarketContext.regime` (already computed once per cycle) |
| Momentum | yes | `MomentumStrategy.analyze()` |
| Mean Reversion | yes | `MeanReversionStrategy.analyze()` |
| Macro | no | the persisted `macro_events` calendar — timing risk only, never direction |
| News Intelligence | yes | `AssetNewsContext.recent_news`, impact/confidence-weighted |
| Sentiment | no | `compute_sentiment_shift` — tone only, never direction (Prompt 6 §11) |
| Quant Research | no | validated `LearnedRule`s for this strategy's scope — evidence only |
| Portfolio Intelligence | no | `packages/portfolio/state.py::compute_state` — exposure/drawdown context |
| Risk Guardian | no | the same safety-belt/loss-streak state the Risk Engine independently re-checks |
| Execution Intelligence | no | recent `Order.expected_price` vs `filled_price` (slippage) |
| Learning | no | rolling `StrategyPerformance`/health-score history, system-wide |
| Anomaly Detection | no | `packages/quant/patterns/detector.py::detect_anomaly` |
| Data Quality | no | `packages/data/quality.py::compute_quality_score` |
| Strategy Health | no | `packages/risk/strategy_health.py::classify_strategy_health` |
| Emergency Guardian | no | kill switch / pause / safety-belt EMERGENCY / auto-kill-switch threshold |

7 agents vote a real direction (`AgentSignal`: `strong_long`/`long`/
`neutral`/`short`/`strong_short`/`no_read`). The other 11 are advisory:
they always report `neutral` and contribute `risk_flags`/evidence instead
— Sentiment and Quant Research are non-directional on principle (a
sentiment tone or a free-form `LearnedRule.conclusion` has no honestly
machine-readable direction), the rest because their job is context, not a
trade idea of their own.

`emergency_guardian`, `risk_guardian`, and `data_quality` are
`CRITICAL_AGENT_CODES` (`packages/agents/protocol.py`) — if any is
`UNAVAILABLE` this cycle, the Chief Decision Engine forces `BLOCKED`
regardless of what every other agent says (Prompt 9 §65: "Se agente
crítico falhar: NO NEW TRADES").

## The protocol

Every specialist is `analyze(ctx: AgentContext) -> AgentMessage`
(`packages/agents/protocol.py`, `context.py`). `AgentMessage` carries
`status` (`ok`/`unavailable`/`quarantined`), `signal`, `confidence`,
`evidence`, `risk_flags`, `rationale`, `generated_at`/`expires_at`. Its
`__post_init__` refuses a non-zero confidence on a non-OK message — "no
hallucinated data" enforced structurally, not by convention. An agent that
cannot form a view (missing data, insufficient history, a raised
exception) reports `UNAVAILABLE` + `NO_READ` + confidence 0, never a
guessed answer.

## Sandbox and permissions

This is a single monolith Python process with no OS-level capability
sandbox. "Sandbox" here means two concrete, re-checked-on-every-test-run
things (`packages/agents/permissions.py`, `tests/test_agent_sandbox.py`),
not a process-isolation guarantee:

1. A declarative permission table of which read-only package each
   specialist may import from.
2. A structural AST proof that no module under `packages/agents/` imports
   `packages.execution` or calls `open_position`/`close_position`/
   `reduce_position` — the same technique
   `tests/test_critical_safety_battery.py` already uses to prove the same
   thing about the rest of the codebase.

## Consensus, Contradiction, Chief Decision

`packages/agents/consensus.py::compute_consensus` — "NÃO É VOTO
MAJORITÁRIO" (Prompt 9 §41). Each directional agent's vote is weighted by
its own reported `confidence` × a reliability weight (`AgentReliability.
reliability_score / 100`, defaulting to a neutral 0.5 with no track record
yet) × a recency weight (0.3 if the message is past its own `expires_at`).
`consensus_score` is in `[-100, 100]`. `meaningful_votes` (agents with
non-zero weight) must be ≥ 2 before the Chief Decision Engine will ever
reach a `*_BIAS` state — a room full of honest zero-confidence NEUTRALs
must never let one agent's lone conviction alone swing the decision.

`packages/agents/contradiction.py::find_contradictions` flags every pair
of directional agents leaning opposite ways, severity = the average of
their two confidences × 100. `contradiction_score` is the worst single
conflict this cycle (max, not average).

`packages/agents/chief.py::decide` is a pure function —
`(messages, reliability_scores) -> Decision` — mirroring
`packages/risk/engine.py::evaluate_signal`'s own purity. `DECISION_STATES`:

```
strong_long_bias / long_bias / neutral / short_bias / strong_short_bias / no_trade / blocked
```

Resolution order:

1. A `CRITICAL_AGENT_CODES` agent is `UNAVAILABLE` → `BLOCKED`.
2. `emergency_guardian`'s `risk_flags` contain `"emergency"` → `BLOCKED`.
3. `contradiction_score >= 70` → `NO_TRADE` (too uncertain to act, not a
   system failure — distinct from `BLOCKED`).
4. Otherwise, `consensus_score` thresholds (±20 lean, ±60 strong), gated
   by `meaningful_votes >= 2`.

## Reliability, calibration, quarantine

`packages/agents/reliability.py` — the same DET-only, "no penalty without
evidence", risk-reducing-direction-only precedent as
`packages/quant/learning/strategy_stats.py` + `quarantine.py`:

- `AgentPrediction` rows are written only for a directional agent's real
  long/short call (never for a NEUTRAL/advisory read).
- `settle_predictions` resolves a prediction against a real candle at or
  after its `evaluate_at` (`get_close_at_or_after`) — never an
  interpolated or guessed price; stays `pending` if no candle exists yet.
- `compute_reliability` returns `None` (writes nothing) below
  `MIN_SAMPLE_FOR_RELIABILITY = 10` settled predictions.
- `overconfidence_gap` = avg confidence on wrong calls − overall accuracy;
  positive means the agent is systematically more confident when it's
  wrong than its hit rate justifies. `reliability_score` is accuracy
  scaled to 0-100, penalized (never rewarded) by that gap.
- Below `RELIABILITY_QUARANTINE_THRESHOLD = 35.0` with enough sample, an
  agent is auto-quarantined (`Agent.status`), the same 35.0 magnitude as
  strategy quarantine. Restoration is always an explicit admin action
  (`POST /api/agents/{code}/restore`, RBAC) — never automatic.

## Wiring into the worker cycle

One `Decision` per `(asset, cycle)` — not per signal/strategy, to keep the
extra pass proportional to the scan rather than to however many signals a
cycle happens to produce. `apps/worker/strategy_runner.py` builds an
`AgentContext` (reusing the already-computed `MarketContext`, plus a fresh
`QualityReport`, `AssetNewsContext`, and the persisted `macro_events`
calendar) and calls `packages/agents/orchestrator.py::run_agent_cycle`
once, before the per-strategy loop.

**Concurrency is deliberately split.** 11 of the 18 specialists are pure
functions of the `AgentContext` and never touch `ctx.db` — those run
genuinely in parallel via `ThreadPoolExecutor` (5s timeout per agent). The
other 7 query `ctx.db`, and SQLAlchemy's `Session` is not safe for
concurrent use across threads — running those in parallel too would
corrupt the shared session's connection state, the same class of problem
`tests/conftest.py`'s SAVEPOINT-isolated `db_session` fixture already
documents. So the DB-touching group runs sequentially in the caller's own
transaction, still individually try/except-isolated so one agent's
exception can never crash the cycle.

`apps/worker/risk_execution.py::maybe_execute` consults the resulting
`Decision` as an **additional** pre-filter, ahead of (never instead of)
the sovereign Risk Engine call that already runs on every signal:

```
tier_filter
  → Chief Decision Engine (BLOCKED/NO_TRADE → stop here, chief_blocked/chief_no_trade)
  → Risk Engine evaluate_signal()      [unchanged from "PROMPT 8"]
  → Portfolio Manager evaluate_allocation()  [unchanged from "PROMPT 8"]
  → open_position()
```

`decision=None` (no multi-agent cycle ran — e.g. a direct test call) is
treated as "no opinion": it neither blocks nor approves anything.
A favorable `Decision` (even `STRONG_LONG_BIAS`) never bypasses a Risk
Engine rejection — proven in `tests/test_agent_worker_wiring.py`.

## API

| Endpoint | Auth |
|---|---|
| `GET /api/agents` | any |
| `GET /api/agents/{code}` | any |
| `GET /api/agents/{code}/messages` | any |
| `POST /api/agents/{code}/restore` | admin |
| `GET /api/decisions` (`?asset_id=&decision_state=&limit=`) | any |
| `GET /api/decisions/{id}` (full trace + contradictions) | any |
| `GET /api/contradictions` (`?decision_id=&limit=`) | any |

## Dashboard — AI Command Center

Agent roster (status/type/reliability/last analysis + a Restore button
when quarantined), Market Consensus (latest `Decision` per asset),
Recent Decisions (click a row to expand the full 18-agent trace, same
pattern as the Opportunities panel's "why" expansion), and Detected
Conflicts.

## Red-team battery (this layer's own attack surface)

Bypass Risk Engine, bypass Portfolio Manager, stale data, exceed
exposure/loss/drawdown, and duplicate-order protection are already covered
by `tests/test_critical_safety_battery.py` and not re-tested here.
`tests/test_agent_consensus_chief.py` covers what's specific to the
multi-agent layer itself — every item below reaches `BLOCKED` or
`NO_TRADE`, never a `*_BIAS` state that could reach execution:

1. `data_quality` (critical) unavailable → `BLOCKED`
2. `emergency_guardian` (critical) unavailable → `BLOCKED`
3. `risk_guardian` (critical) unavailable → `BLOCKED`
4. `emergency_guardian` flags `"emergency"` despite a bullish mob → `BLOCKED`
5. Two strong directional agents contradict → `NO_TRADE`
6. A non-OK message can't carry fabricated confidence (rejected at construction)
7. No `packages/agents/` module imports `packages.execution`
8. No `packages/agents/` module calls `open_position`/`close_position`/`reduce_position`
9. 17 bullish agents can't outvote 1 critical failure → `BLOCKED`
10. `Decision=None` is "no opinion", never implicit approval

## Deliberate divergences from a literal reading of the spec

- `DecisionTrace`/`AgentVersion` as separate tables — folded into
  `Decision.agent_inputs` (a full per-cycle snapshot) and `Agent.version`.
- `LearningProposal` as a new table — `LearnedRule` (Phase 5) already is
  that concept; it only gained a nullable `proposed_by_agent`.
- "Sandbox"/"tool permissions" are structural AST tests, not a runtime
  capability system — this process has no OS-level isolation to offer.
- A literal 18-way `ThreadPoolExecutor` is unsafe with one shared
  SQLAlchemy `Session` — parallel only for the 11 pure agents; correctness
  over a literal reading.
- No DEBATE mode — the per-decision trace is already fully explainable
  without a second LLM round per cycle.
- One `Decision` per `(asset, cycle)`, not per `(asset, strategy, signal)`
  — keeps the extra pass's cost proportional to the scan.
