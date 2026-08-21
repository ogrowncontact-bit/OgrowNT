"""Circuit Breakers & Emergency Kill Switch state machine — "PROMPT 12"
§61-69.

Six named breakers. Four of them wrap an EXISTING enforcement mechanism
that already stops the corresponding kind of risk (this module reports
their status uniformly, it does not duplicate their logic):
  - system    -- the Kill Switch (SystemState.trading_enabled).
  - portfolio -- the Safety Belt's EMERGENCY/KILL_SWITCH levels
                 (packages/risk/safety_belt.py, "PROMPT 4").
  - strategy  -- Strategy Quarantine (StrategyRow.lifecycle_stage ==
                 'quarantine', packages/quant/learning/quarantine.py,
                 Phase 5).
  - asset     -- Asset.status == 'quarantined'
                 (packages/market/universe.py, "PROMPT 11").
Two are genuinely new this phase, built directly on top of
packages/risk/systemic_risk.py's just-added Execution/Data Risk Engines:
  - execution -- trips at ExecutionRiskAssessment.state == CRITICAL.
  - data      -- trips at DataRiskAssessment.state == CRITICAL.

EmergencyKillSwitch is a richer 4-state machine (ARMED/TRIGGERED/LOCKED/
RECOVERY) layered onto the SAME SystemState.trading_enabled boolean every
other kill-switch-aware module already reads — this does not introduce a
second, competing on/off switch. "PROMPT 12" §61-62's governance rule is
enforced structurally: nothing in this module can move the state machine
out of RECOVERY without an explicit `actor` string the CALLER is trusted
to have already authenticated as SUPER_ADMIN (apps/api/deps.py's
require_admin_role precedent — same as every other admin-only mutation in
this codebase). No AI/agent/strategy code path in this repository calls
trigger_kill_switch, start_recovery, or confirm_recovery — grep the
codebase for their call sites to verify.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.risk import safety_belt
from packages.risk.systemic_risk import CRITICAL as _RISK_CRITICAL
from packages.risk.systemic_risk import assess_data_risk, assess_execution_risk, assess_system_risk
from packages.shared.models import Alert, Asset, AuditLog, StrategyRow, SystemState

# -- Circuit breakers ---------------------------------------------------

BREAKER_SYSTEM = "system"
BREAKER_PORTFOLIO = "portfolio"
BREAKER_STRATEGY = "strategy"
BREAKER_ASSET = "asset"
BREAKER_EXECUTION = "execution"
BREAKER_DATA = "data"

CIRCUIT_BREAKER_NAMES = (BREAKER_SYSTEM, BREAKER_PORTFOLIO, BREAKER_STRATEGY, BREAKER_ASSET, BREAKER_EXECUTION, BREAKER_DATA)


@dataclass(frozen=True)
class CircuitBreakerStatus:
    name: str
    tripped: bool
    reason: str | None
    scope_id: int | None = None  # strategy_id or asset_id, for the two per-entity breakers


def system_breaker_status(db: Session) -> CircuitBreakerStatus:
    state = db.get(SystemState, True)
    tripped = state is None or not state.trading_enabled
    reason = "kill switch is tripped" if tripped else None
    return CircuitBreakerStatus(name=BREAKER_SYSTEM, tripped=tripped, reason=reason)


def portfolio_breaker_status(db: Session) -> CircuitBreakerStatus:
    state = db.get(SystemState, True)
    level = state.safety_belt_level if state is not None else safety_belt.EMERGENCY
    tripped = level in (safety_belt.EMERGENCY, safety_belt.KILL_SWITCH)
    reason = f"safety_belt_level={level}" if tripped else None
    return CircuitBreakerStatus(name=BREAKER_PORTFOLIO, tripped=tripped, reason=reason)


def strategy_breaker_status(db: Session, strategy_id: int) -> CircuitBreakerStatus:
    strategy = db.get(StrategyRow, strategy_id)
    tripped = strategy is not None and strategy.lifecycle_stage == "quarantine"
    reason = "strategy is quarantined" if tripped else None
    return CircuitBreakerStatus(name=BREAKER_STRATEGY, tripped=tripped, reason=reason, scope_id=strategy_id)


def asset_breaker_status(db: Session, asset_id: int) -> CircuitBreakerStatus:
    asset = db.get(Asset, asset_id)
    tripped = asset is not None and asset.status == "quarantined"
    reason = "asset is quarantined" if tripped else None
    return CircuitBreakerStatus(name=BREAKER_ASSET, tripped=tripped, reason=reason, scope_id=asset_id)


def execution_breaker_status(db: Session) -> CircuitBreakerStatus:
    assessment = assess_execution_risk(db)
    tripped = assessment.state == _RISK_CRITICAL
    reason = "; ".join(assessment.reasons) if tripped else None
    return CircuitBreakerStatus(name=BREAKER_EXECUTION, tripped=tripped, reason=reason)


def data_breaker_status(db: Session) -> CircuitBreakerStatus:
    assessment = assess_data_risk(db)
    tripped = assessment.state == _RISK_CRITICAL
    reason = "; ".join(assessment.reasons) if tripped else None
    return CircuitBreakerStatus(name=BREAKER_DATA, tripped=tripped, reason=reason)


def portfolio_wide_breaker_statuses(db: Session) -> list[CircuitBreakerStatus]:
    """The 4 breakers that don't need a specific strategy_id/asset_id --
    strategy_breaker_status/asset_breaker_status are evaluated per-entity
    by their own callers instead (there is no single "the" strategy or
    asset to check at the portfolio level)."""
    return [system_breaker_status(db), portfolio_breaker_status(db), execution_breaker_status(db), data_breaker_status(db)]


# -- Emergency Kill Switch state machine ---------------------------------

ARMED = "armed"
TRIGGERED = "triggered"
LOCKED = "locked"
RECOVERY = "recovery"

KILL_SWITCH_STATES = (ARMED, TRIGGERED, LOCKED, RECOVERY)


def trigger_kill_switch(db: Session, *, reason: str, actor: str = "system") -> SystemState:
    """ARMED -> LOCKED (TRIGGERED is a transient instant, not a state worth
    a separate persisted row — the very next read already sees LOCKED).
    Callable automatically (e.g. packages/risk/safety_belt.py::
    should_trigger_kill_switch) or by an admin; never by an AI/agent code
    path — see module docstring."""
    state = db.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = False
    state.kill_switch_state = LOCKED
    state.recovery_mode = False
    state.updated_reason = reason
    state.updated_at = datetime.now(timezone.utc)
    db.add(state)
    db.add(Alert(severity="critical", category="emergency", message=f"Kill switch triggered: {reason}", meta={"actor": actor}))
    db.add(AuditLog(actor=actor, action="kill_switch_triggered", entity_type="system_state", detail={"reason": reason}))
    db.commit()
    return state


def start_recovery(db: Session, *, actor: str) -> SystemState:
    """"PROMPT 12" §61: only a human (SUPER_ADMIN, enforced by the caller —
    apps/api's require_admin_role, same as every other admin-only route)
    may begin recovery. LOCKED -> RECOVERY; trading stays disabled until
    confirm_recovery() succeeds."""
    state = db.get(SystemState, True)
    if state is None or state.kill_switch_state != LOCKED:
        raise ValueError("kill switch is not in LOCKED state -- nothing to recover from")
    state.kill_switch_state = RECOVERY
    state.recovery_mode = True
    state.updated_reason = f"recovery started by {actor}"
    state.updated_at = datetime.now(timezone.utc)
    db.add(state)
    db.add(AuditLog(actor=actor, action="kill_switch_recovery_started", entity_type="system_state", detail={}))
    db.commit()
    return state


@dataclass(frozen=True)
class RecoveryReadiness:
    ready: bool
    reasons: list[str]


def check_recovery_readiness(db: Session, *, now: datetime | None = None) -> RecoveryReadiness:
    """"PROMPT 12" §62's "system health, risk review" gate before recovery
    may complete -- reuses packages/risk/systemic_risk.py's System Risk
    Engine (the same signal apps/api/routers/system.py's health endpoint
    reads) rather than a second health check."""
    now = now or datetime.now(timezone.utc)
    system_risk = assess_system_risk(db, now=now)
    reasons: list[str] = []
    if not system_risk.worker_alive:
        reasons.append("worker heartbeat is stale")
    if system_risk.cadence_failures:
        reasons.append(f"{len(system_risk.cadence_failures)} worker cadence(s) still reporting failures")
    return RecoveryReadiness(ready=not reasons, reasons=reasons)


def confirm_recovery(db: Session, *, actor: str, force: bool = False) -> SystemState:
    """RECOVERY -> ARMED, re-enabling trading. Requires
    check_recovery_readiness() to report ready unless force=True — an
    explicit, itself-audited admin override for the rare case a human has
    reviewed the situation and judges it safe despite a lingering signal
    this function can't see (e.g. a known-flaky data provider being
    replaced)."""
    state = db.get(SystemState, True)
    if state is None or state.kill_switch_state != RECOVERY:
        raise ValueError("kill switch is not in RECOVERY state -- call start_recovery() first")
    readiness = check_recovery_readiness(db)
    if not readiness.ready and not force:
        raise ValueError(f"recovery readiness check failed: {'; '.join(readiness.reasons)}")

    state.kill_switch_state = ARMED
    state.recovery_mode = False
    state.trading_enabled = True
    forced = not readiness.ready and force
    state.updated_reason = f"recovery confirmed by {actor}" + (" (forced despite readiness failures)" if forced else "")
    state.updated_at = datetime.now(timezone.utc)
    db.add(state)
    db.add(
        AuditLog(
            actor=actor, action="kill_switch_recovery_confirmed", entity_type="system_state",
            detail={"forced": forced, "readiness_reasons": readiness.reasons},
        )
    )
    db.add(
        Alert(
            severity="info", category="emergency",
            message=f"Kill switch recovery confirmed by {actor}; trading re-enabled.", meta={"actor": actor, "forced": forced},
        )
    )
    db.commit()
    return state
