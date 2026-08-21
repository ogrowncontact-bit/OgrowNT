"""System / Execution / Model / Data Risk Engines — "PROMPT 12".

Four dimensions the sovereign per-signal `packages/risk/engine.py::
evaluate_signal` pipeline has no way to express on its own, each built by
reusing an EXISTING, already-computed signal rather than a second
implementation:
  - System risk    -- packages/shared/worker_health.py's heartbeat/
                       SystemHealth machinery ("PROMPT 8" §62-66).
  - Execution risk  -- Order.status/slippage_bps, already recorded by
                       packages/execution/order_manager.py on every fill.
  - Model risk      -- Decision.contradiction_score/critical_agent_failure,
                       already computed and persisted every cycle by
                       packages/agents/chief.py ("PROMPT 9" §40-46) — this
                       module reads that column, it does not call
                       find_contradictions() a second time.
  - Data risk       -- Asset.data_quality_score, already refreshed every
                       universe cycle by packages/market/universe.py
                       ("PROMPT 11") via packages/data/quality.py.

All four share the same NORMAL/ELEVATED/HIGH/CRITICAL vocabulary already
established by packages/risk/news_guard.py's News Risk Guard levels
(config/risk_limits.yaml's news_risk_multipliers) rather than inventing a
fifth naming scheme.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.agents.chief import CONTRADICTION_NO_TRADE_THRESHOLD
from packages.data.quality import GOOD_THRESHOLD
from packages.execution.fills import BASE_SLIPPAGE_BPS
from packages.shared.models import Asset, Decision, Order, Position, SystemHealth, SystemState
from packages.shared.settings import get_settings
from packages.shared.worker_health import is_heartbeat_stale

NORMAL = "normal"
ELEVATED = "elevated"
HIGH = "high"
CRITICAL = "critical"

SYSTEMIC_RISK_STATES = (NORMAL, ELEVATED, HIGH, CRITICAL)


# -- System Risk --------------------------------------------------------


@dataclass(frozen=True)
class SystemRiskAssessment:
    state: str
    worker_alive: bool
    kill_switch_tripped: bool
    trading_paused: bool
    cadence_failures: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def assess_system_risk(db: Session, *, now: datetime | None = None) -> SystemRiskAssessment:
    now = now or datetime.now(timezone.utc)
    state = db.get(SystemState, True)
    if state is None:
        return SystemRiskAssessment(
            state=CRITICAL, worker_alive=False, kill_switch_tripped=False, trading_paused=False,
            reasons=["no system_state row found -- system has never initialized"],
        )

    worker_alive = not is_heartbeat_stale(
        state.worker_last_heartbeat, scan_interval_seconds=get_settings().scan_interval_seconds, now=now
    )
    kill_switch_tripped = not state.trading_enabled
    latest_health = db.query(SystemHealth).order_by(SystemHealth.ts.desc()).first()
    cadence_failures = latest_health.cadence_failures if latest_health is not None else {}

    reasons: list[str] = []
    if not worker_alive:
        reasons.append("worker heartbeat is stale -- the trading loop may be down")
    if kill_switch_tripped:
        reasons.append("kill switch is tripped (trading_enabled=False)")
    if cadence_failures:
        reasons.append(f"{len(cadence_failures)} worker cadence(s) reporting failures in the latest health snapshot")
    if state.trading_paused and not reasons:
        reasons.append("trading is manually paused")

    if not worker_alive or kill_switch_tripped:
        level = CRITICAL
    elif cadence_failures:
        level = HIGH
    elif state.trading_paused:
        level = ELEVATED
    else:
        level = NORMAL

    return SystemRiskAssessment(
        state=level, worker_alive=worker_alive, kill_switch_tripped=kill_switch_tripped,
        trading_paused=state.trading_paused, cadence_failures=cadence_failures, reasons=reasons,
    )


# -- Execution Risk -------------------------------------------------------

_EXECUTION_LOOKBACK_LIMIT = 50
_REJECTION_RATE_HIGH = 0.20
_REJECTION_RATE_ELEVATED = 0.10
# Slippage at least double the base assumption baked into packages/execution/
# fills.py::simulate_fill is a genuine execution-quality problem, not noise.
_EXCESS_SLIPPAGE_HIGH_BPS = BASE_SLIPPAGE_BPS * 2
_EXCESS_SLIPPAGE_ELEVATED_BPS = BASE_SLIPPAGE_BPS


@dataclass(frozen=True)
class ExecutionRiskAssessment:
    evaluated: bool
    state: str
    orders_evaluated: int
    rejection_rate: float | None
    avg_slippage_bps: float | None
    reasons: list[str] = field(default_factory=list)


def assess_execution_risk(db: Session, *, lookback: int = _EXECUTION_LOOKBACK_LIMIT) -> ExecutionRiskAssessment:
    recent = (
        db.query(Order)
        .filter(Order.status.in_(("filled", "partially_filled", "rejected")))
        .order_by(Order.id.desc())
        .limit(lookback)
        .all()
    )
    if not recent:
        return ExecutionRiskAssessment(
            evaluated=False, state=NORMAL, orders_evaluated=0, rejection_rate=None, avg_slippage_bps=None,
            reasons=["no recent orders to evaluate"],
        )

    rejected = [o for o in recent if o.status == "rejected"]
    rejection_rate = round(len(rejected) / len(recent), 4)
    slippages = [o.slippage_bps for o in recent if o.slippage_bps is not None]
    avg_slippage = round(sum(slippages) / len(slippages), 4) if slippages else None

    reasons: list[str] = []
    rejection_level = NORMAL
    if rejection_rate >= _REJECTION_RATE_HIGH:
        rejection_level = CRITICAL
        reasons.append(f"order rejection rate {rejection_rate:.1%} over the last {len(recent)} orders")
    elif rejection_rate >= _REJECTION_RATE_ELEVATED:
        rejection_level = HIGH
        reasons.append(f"order rejection rate {rejection_rate:.1%} over the last {len(recent)} orders")

    slippage_level = NORMAL
    if avg_slippage is not None and avg_slippage >= _EXCESS_SLIPPAGE_HIGH_BPS:
        slippage_level = HIGH
        reasons.append(f"average fill slippage {avg_slippage} bps is well above the {BASE_SLIPPAGE_BPS} bps baseline")
    elif avg_slippage is not None and avg_slippage >= _EXCESS_SLIPPAGE_ELEVATED_BPS:
        slippage_level = ELEVATED
        reasons.append(f"average fill slippage {avg_slippage} bps is above the {BASE_SLIPPAGE_BPS} bps baseline")

    level = max(rejection_level, slippage_level, key=SYSTEMIC_RISK_STATES.index)
    return ExecutionRiskAssessment(
        evaluated=True, state=level, orders_evaluated=len(recent), rejection_rate=rejection_rate,
        avg_slippage_bps=avg_slippage, reasons=reasons,
    )


# -- Model Risk -------------------------------------------------------------

_MODEL_RISK_LOOKBACK_MINUTES = 30.0


@dataclass(frozen=True)
class ModelRiskAssessment:
    evaluated: bool
    state: str
    decisions_evaluated: int
    max_contradiction_score: float | None
    any_critical_agent_failure: bool
    reasons: list[str] = field(default_factory=list)


def assess_model_risk(db: Session, *, lookback_minutes: float = _MODEL_RISK_LOOKBACK_MINUTES, now: datetime | None = None) -> ModelRiskAssessment:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=lookback_minutes)
    recent = db.query(Decision).filter(Decision.ts >= cutoff).all()
    if not recent:
        return ModelRiskAssessment(
            evaluated=False, state=NORMAL, decisions_evaluated=0, max_contradiction_score=None,
            any_critical_agent_failure=False, reasons=["no recent Chief Decision Engine output to evaluate"],
        )

    max_contradiction = max(d.contradiction_score for d in recent)
    any_critical_failure = any(d.critical_agent_failure for d in recent)

    reasons: list[str] = []
    if any_critical_failure:
        level = CRITICAL
        reasons.append("a critical agent was unavailable in at least one recent Chief Decision Engine cycle")
    elif max_contradiction >= CONTRADICTION_NO_TRADE_THRESHOLD:
        level = HIGH
        reasons.append(
            f"agent contradiction score reached {max_contradiction} -- at or above Chief Decision Engine's own "
            f"NO_TRADE threshold ({CONTRADICTION_NO_TRADE_THRESHOLD})"
        )
    elif max_contradiction >= CONTRADICTION_NO_TRADE_THRESHOLD * 0.5:
        level = ELEVATED
        reasons.append(f"agent contradiction score reached {max_contradiction}")
    else:
        level = NORMAL

    return ModelRiskAssessment(
        evaluated=True, state=level, decisions_evaluated=len(recent), max_contradiction_score=max_contradiction,
        any_critical_agent_failure=any_critical_failure, reasons=reasons,
    )


# -- Data Risk ----------------------------------------------------------

# Matches packages/data/quality.py::compute_quality_score's own default
# unsafe_threshold -- not re-derived, just referenced with the same value.
_UNSAFE_QUALITY_THRESHOLD = 50


@dataclass(frozen=True)
class DataRiskAssessment:
    evaluated: bool
    state: str
    assets_evaluated: int
    min_quality_score: float | None
    assets_below_threshold: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def assess_data_risk(db: Session) -> DataRiskAssessment:
    open_positions = db.query(Position).filter(Position.status == "open").all()
    if not open_positions:
        return DataRiskAssessment(
            evaluated=False, state=NORMAL, assets_evaluated=0, min_quality_score=None,
            reasons=["no open positions to evaluate"],
        )

    asset_ids = {p.asset_id for p in open_positions}
    assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
    scored = {a.symbol: a.data_quality_score for a in assets if a.data_quality_score is not None}
    if not scored:
        return DataRiskAssessment(
            evaluated=False, state=NORMAL, assets_evaluated=len(assets), min_quality_score=None,
            reasons=["no data_quality_score recorded yet for open positions' assets"],
        )

    min_score = min(scored.values())
    below = sorted(symbol for symbol, score in scored.items() if score < GOOD_THRESHOLD)

    reasons: list[str] = []
    if min_score < _UNSAFE_QUALITY_THRESHOLD:
        level = CRITICAL
        reasons.append(f"at least one open position's asset has a DATA_UNSAFE quality score ({min_score})")
    elif len(below) > 1:
        level = HIGH
        reasons.append(f"{len(below)} open positions' assets have degraded data quality: {', '.join(below)}")
    elif below:
        level = ELEVATED
        reasons.append(f"1 open position's asset has degraded data quality: {below[0]}")
    else:
        level = NORMAL

    return DataRiskAssessment(
        evaluated=True, state=level, assets_evaluated=len(scored), min_quality_score=min_score,
        assets_below_threshold=below, reasons=reasons,
    )
