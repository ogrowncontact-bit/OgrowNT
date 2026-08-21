"""Capital Defense cadence — "PROMPT 12" §107-108's Risk Event Timeline /
periodic risk reports.

Runs AdvancedRiskEngine (packages/risk/advanced_engine.py) on its own
cadence, independent of the strategy cycle. Unlike the per-signal
advanced_risk context apps/worker/strategy_runner.py already threads into
evaluate_signal() (computed once per strategy cycle, only when the
strategy cadence actually fires), this persists a RiskAssessment row on
EVERY tick regardless of whether any signal arrived — the "written on
every engine cycle" precedent packages/shared/models.py's RiskAssessment
docstring already documents — and keeps SystemState.capital_preservation_
mode/zero_trade_mode fresh for any caller that reads them directly
(dashboard, API) without recomputing the whole assessment itself.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.risk.advanced_engine import AdvancedRiskAssessment, assess_portfolio_risk
from packages.risk.config import load_risk_limits
from packages.shared.models import Alert, RiskAssessment, SystemState

logger = logging.getLogger("worker.capital_defense")

# RiskStates at/above which a FRESH escalation (a transition into elevated
# risk, not every tick while already there) is worth an Alert — matches
# capital_preservation_mode's own HIGH_RISK+ threshold
# (packages/risk/advanced_engine.py).
_ALERT_WORTHY_STATES = {"high_risk", "critical", "emergency", "halted"}
_SEVERE_STATES = {"emergency", "halted"}


def _persist_assessment(db: Session, assessment: AdvancedRiskAssessment) -> RiskAssessment:
    row = RiskAssessment(
        ts=assessment.ts, risk_score=assessment.risk_score, risk_state=assessment.risk_state,
        drawdown_state=assessment.drawdown.risk_state if assessment.drawdown else None,
        correlation_state=assessment.concentration.concentration_state if assessment.concentration else None,
        # volatility_state/liquidity_state/event_state: no dedicated
        # AdvancedRiskEngine dimension for these yet (see
        # packages/risk/advanced_engine.py's module docstring) -- left
        # honestly None rather than duplicated from another module.
        volatility_state=None, liquidity_state=None, event_state=None,
        model_state=assessment.model_risk.state if assessment.model_risk else None,
        data_state=assessment.data_risk.state if assessment.data_risk else None,
        system_state=assessment.system_risk.state if assessment.system_risk else None,
        execution_state=assessment.execution_risk.state if assessment.execution_risk else None,
        capital_preservation_mode=assessment.capital_preservation_mode,
        zero_trade_mode=assessment.zero_trade_mode,
        reasons=assessment.reasons,
    )
    db.add(row)
    return row


def run_capital_defense_cycle(db: Session) -> AdvancedRiskAssessment:
    limits = load_risk_limits()
    assessment = assess_portfolio_risk(db, limits)

    state = db.get(SystemState, True) or SystemState(id=True)
    was_elevated = state.capital_preservation_mode or state.zero_trade_mode

    state.capital_preservation_mode = assessment.capital_preservation_mode
    state.zero_trade_mode = assessment.zero_trade_mode
    db.add(state)

    _persist_assessment(db, assessment)

    is_elevated = assessment.capital_preservation_mode or assessment.zero_trade_mode
    if assessment.risk_state in _ALERT_WORTHY_STATES and not was_elevated:
        db.add(
            Alert(
                severity="critical" if assessment.risk_state in _SEVERE_STATES else "warning",
                category="risk",
                message=f"Advanced Risk Engine escalated to {assessment.risk_state} (score={assessment.risk_score})",
                meta={"risk_state": assessment.risk_state, "risk_score": assessment.risk_score, "reasons": assessment.reasons},
            )
        )
    elif was_elevated and not is_elevated:
        db.add(
            Alert(
                severity="info", category="risk",
                message=f"Advanced Risk Engine returned to {assessment.risk_state} -- capital preservation mode lifted.",
                meta={"risk_state": assessment.risk_state, "risk_score": assessment.risk_score},
            )
        )

    db.commit()
    logger.info(
        "Capital defense cycle: risk_state=%s risk_score=%.1f capital_preservation=%s zero_trade=%s degraded=%s",
        assessment.risk_state, assessment.risk_score, assessment.capital_preservation_mode,
        assessment.zero_trade_mode, assessment.degraded,
    )
    return assessment
