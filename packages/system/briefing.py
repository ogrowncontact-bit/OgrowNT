"""Daily/Hourly AI Briefing — "PROMPT 14" §78-81.

Pure read-side aggregation over data other modules already compute — same
"called on demand, never a worker cadence, no new persisted table" role
packages/analytics/overview.py already plays for the dashboard's Advanced
Analytics panel (Phase 7). A briefing IS its inputs at read time, not a
historical claim worth persisting on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.portfolio.state import compute_state
from packages.shared.models import Alert, Incident, OpportunityScore, Position, SystemState, Trade


@dataclass(frozen=True)
class DailyBriefing:
    generated_at: datetime
    window_hours: int
    equity: float
    daily_pnl: float
    drawdown_pct: float
    trades_closed: int
    win_rate: float | None
    open_positions: int
    top_opportunity_count: int
    active_incidents: int
    unacknowledged_alerts: int
    safety_belt_level: str
    trading_enabled: bool


def generate_daily_briefing(db: Session, *, window_hours: int = 24) -> DailyBriefing:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours)
    state = compute_state(db)
    system_state = db.get(SystemState, True)

    closed_trades = db.execute(select(Trade).where(Trade.closed_at >= since)).scalars().all()
    wins = sum(1 for t in closed_trades if t.outcome == "win")
    win_rate = round(wins / len(closed_trades), 4) if closed_trades else None

    return DailyBriefing(
        generated_at=now,
        window_hours=window_hours,
        equity=state.equity,
        daily_pnl=state.daily_pnl,
        drawdown_pct=state.drawdown_pct,
        trades_closed=len(closed_trades),
        win_rate=win_rate,
        open_positions=db.query(Position).filter(Position.status == "open").count(),
        top_opportunity_count=db.query(OpportunityScore).filter(OpportunityScore.tier.in_(("high_quality", "exceptional"))).count(),
        active_incidents=db.query(Incident).filter(Incident.status.notin_(("resolved", "closed"))).count(),
        unacknowledged_alerts=db.query(Alert).filter(Alert.acknowledged.is_(False)).count(),
        safety_belt_level=system_state.safety_belt_level if system_state else "normal",
        trading_enabled=system_state.trading_enabled if system_state else True,
    )
