"""Advanced Risk Engine — "PROMPT 12" §1-15's RiskScore/RiskState
aggregation layer.

Composes every dimension built for this phase (capital/drawdown,
concentration, loss streak, system/execution/model/data risk, circuit
breakers) into ONE portfolio-wide assessment. This does NOT replace the
sovereign per-signal `packages/risk/engine.py::evaluate_signal` pipeline —
it feeds it richer context (wired in a later task) and adds dimensions
that pipeline's safety_belt-driven logic cannot express on its own.

RiskScore is explicitly NOT a probability of loss (§9: "RiskScore NÃO
representa probabilidade de perda. É um indicador composto de condições de
risco.") — it is a fixed-weight blend of independently-computed dimension
severities, same style as packages/quant/learning/strategy_stats.py's own
health_score.

RiskState aggregation is a MAX across dimensions, never an average: "nenhum
nível inferior pode substituir um nível superior" (§9) is enforced
structurally by using max() over the ordered RISK_STATES tuple, not by
convention. HALTED is reserved for a tripped system/portfolio circuit
breaker (packages/risk/circuit_breakers.py) — no combination of drawdown,
concentration, or systemic-risk dimensions alone can reach it; drawdown's
own ladder tops out at EMERGENCY (see packages/risk/capital_state.py).

Fail-closed (§ "Se o sistema não sabe se é seguro: NÃO operar"): if any
single dimension's computation raises, that dimension is NOT silently
skipped — it fails closed to HALTED for its own contribution, `degraded`
is set on the result, and the failure is recorded in `reasons`. A partial
or erroring picture can only ever push the aggregate MORE conservative,
never less.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.risk import circuit_breakers as cb
from packages.risk import concentration as conc
from packages.risk import systemic_risk as sysrisk
from packages.risk.capital_state import (
    CAUTION,
    CRITICAL,
    DEFENSIVE,
    EMERGENCY,
    HALTED,
    HIGH_RISK,
    NORMAL,
    RISK_STATES,
    CapitalState,
    DrawdownAssessment,
    assess_drawdown,
    compute_capital_state,
)
from packages.risk.config import RiskLimits
from packages.risk.loss_streak import LossStreakResult, evaluate_loss_streak

# Fixed weights (sum to 1.0), same "documented assumption, not a fitted
# model" convention as strategy_stats.py's _HEALTH_WEIGHTS. Drawdown gets
# the largest single weight -- it is the one dimension with its own
# configurable, spec-mandated response ladder (config/risk_limits.yaml's
# drawdown_levels).
_WEIGHTS = {
    "drawdown": 0.30,
    "concentration": 0.15,
    "system": 0.15,
    "execution": 0.10,
    "model": 0.10,
    "data": 0.10,
    "loss_streak": 0.10,
}

# systemic_risk.py's NORMAL/ELEVATED/HIGH/CRITICAL -> this module's 7-level
# vocabulary. A systemic CRITICAL maps to CRITICAL here, never EMERGENCY/
# HALTED -- those stay reserved for drawdown's own ladder and circuit
# breakers respectively (see module docstring).
_SYSTEMIC_STATE_MAP = {
    sysrisk.NORMAL: NORMAL, sysrisk.ELEVATED: CAUTION, sysrisk.HIGH: DEFENSIVE, sysrisk.CRITICAL: CRITICAL,
}
_CONCENTRATION_STATE_MAP = {
    conc.LOW: NORMAL, conc.MODERATE: CAUTION, conc.HIGH: DEFENSIVE, conc.CONCENTRATED: HIGH_RISK,
}


def _severity(state: str) -> float:
    return RISK_STATES.index(state) / (len(RISK_STATES) - 1) * 100


@dataclass(frozen=True)
class AdvancedRiskAssessment:
    ts: datetime
    risk_score: float
    risk_state: str
    capital_state: CapitalState | None
    drawdown: DrawdownAssessment | None
    concentration: conc.ConcentrationAssessment | None
    loss_streak: LossStreakResult | None
    system_risk: sysrisk.SystemRiskAssessment | None
    execution_risk: sysrisk.ExecutionRiskAssessment | None
    model_risk: sysrisk.ModelRiskAssessment | None
    data_risk: sysrisk.DataRiskAssessment | None
    breakers: list[cb.CircuitBreakerStatus]
    capital_preservation_mode: bool
    zero_trade_mode: bool
    degraded: bool
    reasons: list[str] = field(default_factory=list)


def assess_portfolio_risk(db: Session, limits: RiskLimits, *, now: datetime | None = None) -> AdvancedRiskAssessment:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    degraded = False
    dimension_states: dict[str, str] = {}

    capital_state: CapitalState | None = None
    drawdown: DrawdownAssessment | None = None
    try:
        capital_state = compute_capital_state(db)
        drawdown = assess_drawdown(db, limits, capital_state.drawdown_pct, now=now)
        dimension_states["drawdown"] = drawdown.risk_state
        if drawdown.level > 0:
            reasons.append(f"drawdown at DD_LEVEL_{drawdown.level}: {drawdown.response} (effective {drawdown.effective_drawdown_pct}%)")
    except Exception as exc:  # noqa: BLE001 -- fail-closed: never let a computation error read as "safe"
        degraded = True
        dimension_states["drawdown"] = HALTED
        reasons.append(f"capital/drawdown assessment failed ({exc}) -- failing closed")

    concentration: conc.ConcentrationAssessment | None = None
    try:
        equity = capital_state.equity if capital_state is not None else 0.0
        concentration = conc.assess_concentration(db, limits, equity)
        dimension_states["concentration"] = _CONCENTRATION_STATE_MAP[concentration.concentration_state]
        reasons.extend(concentration.hidden_factor_warnings)
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["concentration"] = HALTED
        reasons.append(f"concentration assessment failed ({exc}) -- failing closed")

    loss_streak: LossStreakResult | None = None
    try:
        loss_streak = evaluate_loss_streak(db, limits.loss_streak)
        dimension_states["loss_streak"] = CAUTION if loss_streak.triggered else NORMAL
        if loss_streak.triggered:
            reasons.append(f"portfolio-wide loss streak active ({loss_streak.consecutive_losses} consecutive losses)")
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["loss_streak"] = HALTED
        reasons.append(f"loss streak assessment failed ({exc}) -- failing closed")

    system_risk: sysrisk.SystemRiskAssessment | None = None
    try:
        system_risk = sysrisk.assess_system_risk(db, now=now)
        dimension_states["system"] = _SYSTEMIC_STATE_MAP[system_risk.state]
        reasons.extend(system_risk.reasons)
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["system"] = HALTED
        reasons.append(f"system risk assessment failed ({exc}) -- failing closed")

    execution_risk: sysrisk.ExecutionRiskAssessment | None = None
    try:
        execution_risk = sysrisk.assess_execution_risk(db)
        dimension_states["execution"] = _SYSTEMIC_STATE_MAP[execution_risk.state]
        reasons.extend(execution_risk.reasons)
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["execution"] = HALTED
        reasons.append(f"execution risk assessment failed ({exc}) -- failing closed")

    model_risk: sysrisk.ModelRiskAssessment | None = None
    try:
        model_risk = sysrisk.assess_model_risk(db, now=now)
        dimension_states["model"] = _SYSTEMIC_STATE_MAP[model_risk.state]
        reasons.extend(model_risk.reasons)
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["model"] = HALTED
        reasons.append(f"model risk assessment failed ({exc}) -- failing closed")

    data_risk: sysrisk.DataRiskAssessment | None = None
    try:
        data_risk = sysrisk.assess_data_risk(db)
        dimension_states["data"] = _SYSTEMIC_STATE_MAP[data_risk.state]
        reasons.extend(data_risk.reasons)
    except Exception as exc:  # noqa: BLE001
        degraded = True
        dimension_states["data"] = HALTED
        reasons.append(f"data risk assessment failed ({exc}) -- failing closed")

    breakers: list[cb.CircuitBreakerStatus] = []
    breaker_override: str | None = None
    try:
        breakers = cb.portfolio_wide_breaker_statuses(db)
        system_or_portfolio_tripped = any(b.tripped for b in breakers if b.name in (cb.BREAKER_SYSTEM, cb.BREAKER_PORTFOLIO))
        other_tripped = any(b.tripped for b in breakers if b.name in (cb.BREAKER_EXECUTION, cb.BREAKER_DATA))
        if system_or_portfolio_tripped:
            breaker_override = HALTED
            reasons.append("system or portfolio circuit breaker is tripped")
        elif other_tripped:
            breaker_override = EMERGENCY
            reasons.append("execution or data circuit breaker is tripped")
    except Exception as exc:  # noqa: BLE001
        degraded = True
        breaker_override = HALTED
        reasons.append(f"circuit breaker check failed ({exc}) -- failing closed")

    all_states = list(dimension_states.values()) + ([breaker_override] if breaker_override is not None else [])
    risk_state = max(all_states, key=RISK_STATES.index) if all_states else NORMAL

    # The weighted blend is the genuine composite score -- since weights sum
    # to 1.0 and every dimension's severity is by definition <= the max
    # dimension's own severity, a floor at severity(risk_state) here would
    # make the blend mathematically unreachable (weighted_score can never
    # exceed that floor), silently turning the "composite indicator of risk
    # conditions" into nothing more than a mirror of risk_state -- exactly
    # what §9's "RiskScore is not a probability, it's a composite" wants to
    # avoid. A floor is only applied when a circuit breaker actually
    # tripped (breaker_override is not None): that is a structurally
    # different, discrete kind of severity a smooth weighted blend across
    # 7 dimensions could otherwise understate.
    weighted_score = sum(_WEIGHTS[dim] * _severity(state) for dim, state in dimension_states.items() if dim in _WEIGHTS)
    if breaker_override is not None:
        risk_score = round(max(weighted_score, _severity(breaker_override)), 2)
    else:
        risk_score = round(weighted_score, 2)

    capital_preservation_mode = RISK_STATES.index(risk_state) >= RISK_STATES.index(HIGH_RISK)
    zero_trade_mode = RISK_STATES.index(risk_state) >= RISK_STATES.index(CRITICAL)

    return AdvancedRiskAssessment(
        ts=now, risk_score=risk_score, risk_state=risk_state, capital_state=capital_state, drawdown=drawdown,
        concentration=concentration, loss_streak=loss_streak, system_risk=system_risk, execution_risk=execution_risk,
        model_risk=model_risk, data_risk=data_risk, breakers=breakers,
        capital_preservation_mode=capital_preservation_mode, zero_trade_mode=zero_trade_mode,
        degraded=degraded, reasons=reasons,
    )
