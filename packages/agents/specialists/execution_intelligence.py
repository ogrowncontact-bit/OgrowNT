"""Execution Intelligence Agent — "PROMPT 9" §34. Reads the execution-
quality fields "PROMPT 8" already captures on every `Order`
(`expected_price` vs `filled_price`, `latency_ms`) for this asset's recent
fills — never a live orderbook/spread feed (this system has none, honestly
documented in `packages/risk/engine.py`'s liquidity check) — to flag when
recent fills have been slipping badly, context for the Chief Decision
Engine rather than a new gate.
"""
from __future__ import annotations

from sqlalchemy import select

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.shared.models import Order, Position

AGENT_CODE = "execution_intelligence"
LOOKBACK_FILLS = 10
SLIPPAGE_WARNING_BPS = 25.0


def analyze(ctx: AgentContext) -> AgentMessage:
    rows = ctx.db.execute(
        select(Order)
        .join(Position, Position.id == Order.position_id)
        .where(Position.asset_id == ctx.asset.id, Order.status == "filled", Order.expected_price.isnot(None), Order.filled_price.isnot(None))
        .order_by(Order.filled_at.desc())
        .limit(LOOKBACK_FILLS)
    ).scalars().all()

    if not rows:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"recent_fills": 0}, rationale="no recent fills with execution-quality data for this asset",
        )

    slippage_bps = [
        abs(o.filled_price - o.expected_price) / o.expected_price * 10_000
        for o in rows if o.expected_price and o.filled_price is not None
    ]
    avg_slippage = round(sum(slippage_bps) / len(slippage_bps), 2) if slippage_bps else 0.0
    latencies = [o.latency_ms for o in rows if o.latency_ms is not None]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None

    risk_flags = ("execution_quality_degraded",) if avg_slippage >= SLIPPAGE_WARNING_BPS else ()
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=round(min(1.0, avg_slippage / (SLIPPAGE_WARNING_BPS * 2)), 4),
        evidence={"recent_fills": len(rows), "avg_slippage_bps": avg_slippage, "avg_latency_ms": avg_latency},
        risk_flags=risk_flags,
        rationale=f"avg slippage over last {len(rows)} fill(s): {avg_slippage}bps",
    )
