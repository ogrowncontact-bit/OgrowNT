"""Portfolio Engine — docs/blueprint/04-agents-architecture.md#agent-10.

Owns the single source of truth for the paper account's cash/equity: the
`portfolio_snapshots` table. Nothing else writes to it — the Execution
Engine calls `refresh_snapshot()` after every fill, and the worker calls it
on its own cadence so equity/drawdown stay current even between fills
(prices move; unrealized P&L on open positions moves with them).

Cash model (paper trading simplification, not real margin mechanics):
opening a position reserves its notional (entry_price * size) plus fees;
closing a position returns that notional plus the position's realized P&L
minus exit fees. This is direction-agnostic (same accounting for long and
short) — good enough for evaluating strategies/risk without modeling real
short-selling collateral, which would be overkill for paper trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.shared.market_data import get_latest_close
from packages.shared.models import PortfolioSnapshot, Position, SystemState
from packages.shared.settings import get_settings


@dataclass(frozen=True)
class PortfolioState:
    ts: datetime
    cash: float
    equity: float
    exposure_pct: float
    daily_pnl: float
    daily_loss_pct: float  # 0 unless daily_pnl is negative — see safety_belt.py
    weekly_pnl: float
    weekly_loss_pct: float
    monthly_pnl: float
    monthly_loss_pct: float
    drawdown_pct: float
    unrealized_pnl: float
    open_positions: list[Position]


def _reset_epoch(db: Session) -> datetime | None:
    """RESET PAPER ACCOUNT's cutoff (SystemState.last_reset_at): every
    PortfolioSnapshot before it is still real history (append-only, never
    deleted — see that column's docstring) but must stop counting toward
    peak-equity/drawdown/period-P&L math, or a reset would immediately
    read as a huge fake drawdown against a peak from a life the account no
    longer has."""
    state = db.get(SystemState, True)
    return state.last_reset_at if state is not None else None


def get_latest_cash(db: Session) -> float:
    epoch = _reset_epoch(db)
    query = select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
    if epoch is not None:
        query = query.where(PortfolioSnapshot.ts >= epoch)
    latest = db.execute(query).scalar_one_or_none()
    if latest is None:
        return get_settings().initial_paper_capital
    return latest.cash


def _peak_equity(db: Session, current_equity: float, epoch: datetime | None) -> float:
    query = select(func.max(PortfolioSnapshot.equity))
    if epoch is not None:
        query = query.where(PortfolioSnapshot.ts >= epoch)
    historical_max = db.execute(query).scalar_one_or_none()
    return max(historical_max or 0.0, current_equity)


def get_reset_epoch(db: Session) -> datetime | None:
    """Public entry point for "PROMPT 12"'s CapitalState.realized_pnl —
    the same RESET PAPER ACCOUNT cutoff _reset_epoch() already applies to
    every other period-P&L query in this module, exposed once rather than
    reimplemented by a caller outside this module."""
    return _reset_epoch(db)


def get_peak_equity(db: Session, current_equity: float | None = None) -> float:
    """Public entry point for "PROMPT 12"'s CapitalState.peak_equity —
    _peak_equity() above already computes this for the drawdown_pct math
    inline; this just exposes the same reset-epoch-aware query rather than
    a second implementation.
    """
    epoch = _reset_epoch(db)
    current_equity = get_latest_cash(db) if current_equity is None else current_equity
    return _peak_equity(db, current_equity, epoch)


def _equity_at_start_of_day(db: Session, now: datetime, epoch: datetime | None) -> float:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if epoch is not None and epoch > day_start:
        day_start = epoch  # the account's day effectively started at reset, not midnight
    first_today = db.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.ts >= day_start).order_by(PortfolioSnapshot.ts.asc()).limit(1)
    ).scalar_one_or_none()
    if first_today is not None:
        return first_today.equity
    before_query = select(PortfolioSnapshot).where(PortfolioSnapshot.ts < day_start).order_by(PortfolioSnapshot.ts.desc()).limit(1)
    if epoch is not None:
        before_query = before_query.where(PortfolioSnapshot.ts >= epoch)
    last_before_today = db.execute(before_query).scalar_one_or_none()
    if last_before_today is not None:
        return last_before_today.equity
    return get_settings().initial_paper_capital


def _equity_n_days_ago(db: Session, now: datetime, days: int, epoch: datetime | None) -> float:
    cutoff = now - timedelta(days=days)
    if epoch is not None and epoch > cutoff:
        cutoff = epoch
    closest_before = db.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.ts <= cutoff).order_by(PortfolioSnapshot.ts.desc()).limit(1)
    ).scalar_one_or_none()
    if closest_before is not None:
        return closest_before.equity
    earliest_query = select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.asc()).limit(1)
    if epoch is not None:
        earliest_query = earliest_query.where(PortfolioSnapshot.ts >= epoch)
    earliest = db.execute(earliest_query).scalar_one_or_none()
    return earliest.equity if earliest is not None else get_settings().initial_paper_capital


def compute_state(db: Session, cash: float | None = None, timeframe: str = "1m") -> PortfolioState:
    """Pure computation — does not write anything. `cash` overrides the
    latest ledger value, for callers that just changed it (Execution Engine
    mid-fill, before the new snapshot exists yet).
    """
    now = datetime.now(timezone.utc)
    epoch = _reset_epoch(db)
    cash = get_latest_cash(db) if cash is None else cash
    open_positions = db.query(Position).filter(Position.status == "open").all()

    unrealized_pnl = 0.0
    exposure_notional = 0.0
    for position in open_positions:
        price = get_latest_close(db, position.asset_id, timeframe)
        if price is None:
            continue  # DATA_UNAVAILABLE for this asset — mark-to-market skipped, not faked
        direction_mult = 1 if position.direction == "long" else -1
        unrealized_pnl += (price - position.entry_price) * position.size * direction_mult
        exposure_notional += position.entry_price * position.size

    equity = cash + exposure_notional + unrealized_pnl
    exposure_pct = (exposure_notional / equity * 100) if equity > 0 else 0.0

    peak = _peak_equity(db, equity, epoch)
    drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0.0

    equity_day_start = _equity_at_start_of_day(db, now, epoch)
    daily_pnl = equity - equity_day_start
    daily_loss_pct = max(0.0, -daily_pnl) / equity_day_start * 100 if equity_day_start > 0 else 0.0

    equity_week_start = _equity_n_days_ago(db, now, 7, epoch)
    weekly_pnl = equity - equity_week_start
    weekly_loss_pct = max(0.0, -weekly_pnl) / equity_week_start * 100 if equity_week_start > 0 else 0.0

    # Monthly window: a fixed 30-day lookback (same approach as weekly's
    # fixed 7-day lookback), not calendar-month-to-date — simpler and
    # avoids a discontinuity on the 1st where "monthly" loss would
    # otherwise reset to near-zero mid-drawdown.
    equity_month_start = _equity_n_days_ago(db, now, 30, epoch)
    monthly_pnl = equity - equity_month_start
    monthly_loss_pct = max(0.0, -monthly_pnl) / equity_month_start * 100 if equity_month_start > 0 else 0.0

    return PortfolioState(
        ts=now,
        cash=cash,
        equity=equity,
        exposure_pct=round(exposure_pct, 4),
        daily_pnl=round(daily_pnl, 2),
        daily_loss_pct=round(daily_loss_pct, 4),
        weekly_pnl=round(weekly_pnl, 2),
        weekly_loss_pct=round(weekly_loss_pct, 4),
        monthly_pnl=round(monthly_pnl, 2),
        monthly_loss_pct=round(monthly_loss_pct, 4),
        drawdown_pct=round(drawdown_pct, 4),
        unrealized_pnl=round(unrealized_pnl, 2),
        open_positions=open_positions,
    )


def refresh_snapshot(db: Session, cash: float | None = None, safety_belt_level: str = "normal") -> PortfolioSnapshot:
    """The only writer of portfolio_snapshots. Computes fresh state and
    appends a new row — never mutates a past snapshot (append-only, so
    drawdown/history stay auditable)."""
    state = compute_state(db, cash=cash)
    snapshot = PortfolioSnapshot(
        ts=state.ts,
        equity=state.equity,
        cash=state.cash,
        exposure_pct=state.exposure_pct,
        daily_pnl=state.daily_pnl,
        drawdown_pct=state.drawdown_pct,
        safety_belt_level=safety_belt_level,
    )
    db.add(snapshot)
    db.commit()
    return snapshot
