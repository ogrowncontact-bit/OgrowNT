"""Portfolio Intelligence Agent — "PROMPT 9" §32. Reads
`packages/portfolio/state.py::compute_state` — the same exposure/drawdown
numbers the Risk Engine and Portfolio Manager already gate on — purely as
context for the Chief Decision Engine, never as a second gate: this agent
cannot block anything, it only flags when the book is already close to a
limit so a HIGH-conviction alpha vote can be weighed against "there's
little room left anyway".
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.portfolio.state import compute_state
from packages.risk.config import load_risk_limits

AGENT_CODE = "portfolio_intelligence"
HEADROOM_WARNING_PCT = 5.0  # within 5 percentage points of the portfolio exposure ceiling


def analyze(ctx: AgentContext) -> AgentMessage:
    state = compute_state(ctx.db)
    limits = load_risk_limits()
    headroom_pct = round(limits.portfolio.max_exposure_pct - state.exposure_pct, 4)

    risk_flags = []
    if headroom_pct <= HEADROOM_WARNING_PCT:
        risk_flags.append("portfolio_exposure_near_limit")
    if state.drawdown_pct >= limits.loss_limits.max_portfolio_drawdown_pct * 0.7:
        risk_flags.append("drawdown_approaching_emergency")

    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=1.0,
        evidence={
            "exposure_pct": state.exposure_pct, "headroom_pct": headroom_pct, "drawdown_pct": state.drawdown_pct,
            "open_positions": len(state.open_positions), "equity": state.equity,
        },
        risk_flags=tuple(risk_flags),
        rationale=f"exposure={state.exposure_pct}% headroom={headroom_pct}% drawdown={state.drawdown_pct}%",
    )
