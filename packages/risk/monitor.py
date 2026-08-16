"""Keeps system_state.safety_belt_level in sync with the portfolio's actual
risk metrics — docs/blueprint/08-risk-engine.md#risk-states-safety-belts.
Called once per worker cycle (apps/worker/main.py), independent of whether
any signal fired this cycle: drawdown moves with price even without a
new trade.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.portfolio.state import compute_state
from packages.risk.config import load_risk_limits
from packages.risk.safety_belt import CAUTION, DEFENSIVE, EMERGENCY, KILL_SWITCH, NORMAL, evaluate_safety_belt, should_trigger_kill_switch
from packages.shared.models import Alert, AuditLog, SystemState

logger = logging.getLogger("worker.risk_monitor")

# docs/blueprint/08-risk-engine.md#safe-mode calls out severity=critical on
# entering a kill-switch/emergency state explicitly; the rest is a judgment
# call kept conservative (any belt tightening is at least a warning).
_ALERT_SEVERITY_BY_BELT = {
    NORMAL: "info",
    CAUTION: "warning",
    DEFENSIVE: "warning",
    EMERGENCY: "critical",
    KILL_SWITCH: "critical",
}


def update_safety_belt(db: Session) -> str:
    limits = load_risk_limits()
    state = compute_state(db)
    system_state = db.get(SystemState, True) or SystemState(id=True)
    previous_level = system_state.safety_belt_level

    if previous_level == KILL_SWITCH:
        # Only an explicit admin action (POST /api/system/kill-switch/release)
        # clears this — docs/blueprint/08-risk-engine.md#kill-switch.
        return previous_level

    if should_trigger_kill_switch(state, limits):
        new_level = KILL_SWITCH
        system_state.trading_enabled = False
        db.add(
            AuditLog(
                actor="risk_engine",
                action="kill_switch_triggered",
                entity_type="system_state",
                detail={"trigger": "auto", "drawdown_pct": state.drawdown_pct},
            )
        )
        logger.warning("KILL SWITCH auto-triggered: drawdown_pct=%.2f", state.drawdown_pct)
    else:
        new_level = evaluate_safety_belt(state, limits)

    if new_level != previous_level:
        db.add(
            AuditLog(
                actor="risk_engine",
                action="safety_belt_changed",
                entity_type="system_state",
                detail={"from": previous_level, "to": new_level, "drawdown_pct": state.drawdown_pct},
            )
        )
        db.add(
            Alert(
                severity=_ALERT_SEVERITY_BY_BELT.get(new_level, "warning"),
                category="risk" if new_level != KILL_SWITCH else "emergency",
                message=f"Safety belt changed: {previous_level} -> {new_level} (drawdown {state.drawdown_pct:.2f}%)",
                meta={"from": previous_level, "to": new_level, "drawdown_pct": state.drawdown_pct},
            )
        )
        logger.info("Safety belt: %s -> %s", previous_level, new_level)

    system_state.safety_belt_level = new_level
    system_state.updated_reason = f"auto: drawdown={state.drawdown_pct:.2f}% daily_loss={state.daily_loss_pct:.2f}%"
    db.add(system_state)
    db.commit()
    return new_level
