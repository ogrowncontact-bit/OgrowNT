"""Emergency Guardian Agent — "PROMPT 9" §36, one of CRITICAL_AGENT_CODES.

Reads the same `SystemState`/`PortfolioState` the real Kill Switch already
gates on (`packages/risk/safety_belt.py`) — never a second implementation
of that logic, purely a read for the multi-agent layer's own honesty: if
the sovereign Risk Engine would already refuse every new trade this cycle
(kill switch tripped, trading paused, EMERGENCY belt, or the automatic
kill-switch-recommended threshold), this agent's "emergency" risk_flag
tells the Chief Decision Engine to reach the same BLOCKED conclusion
independently, rather than silently disagreeing with the layer underneath
it. It has zero power to actually stop trading itself — packages/risk/
safety_belt.py and packages/risk/engine.py remain the only real gate.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.portfolio.state import compute_state
from packages.risk.config import load_risk_limits
from packages.risk.safety_belt import EMERGENCY, KILL_SWITCH, evaluate_safety_belt, should_trigger_kill_switch
from packages.shared.models import SystemState

AGENT_CODE = "emergency_guardian"


def analyze(ctx: AgentContext) -> AgentMessage:
    system_state = ctx.db.get(SystemState, True)
    if system_state is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.0,
            evidence={"reason": "no_system_state_row"}, rationale="no_system_state_row",
        )

    limits = load_risk_limits()
    portfolio_state = compute_state(ctx.db)
    belt = evaluate_safety_belt(portfolio_state, limits)

    risk_flags = []
    if not system_state.trading_enabled:
        risk_flags.append("kill_switch_active")
    if system_state.trading_paused:
        risk_flags.append("trading_paused")
    if belt in (EMERGENCY, KILL_SWITCH):
        risk_flags.append("safety_belt_emergency")
    if should_trigger_kill_switch(portfolio_state, limits):
        risk_flags.append("kill_switch_recommended")
    if "emergency" not in risk_flags and risk_flags:
        risk_flags.append("emergency")  # the umbrella flag chief.py's BLOCKED rule keys on

    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=1.0,
        evidence={
            "trading_enabled": system_state.trading_enabled, "trading_paused": system_state.trading_paused,
            "safety_belt": belt, "drawdown_pct": portfolio_state.drawdown_pct,
        },
        risk_flags=tuple(risk_flags),
        rationale="emergency conditions active" if risk_flags else "no emergency conditions",
    )
