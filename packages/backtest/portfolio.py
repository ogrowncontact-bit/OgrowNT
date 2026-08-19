"""Simulated portfolio for the Backtest Engine — an isolated, in-memory
account, never touching the live `positions`/`orders`/`portfolio_snapshots`
tables (a backtest must never corrupt the real paper account). Mirrors the
exact cash/P&L accounting `packages/execution/order_manager.py` uses in
production (open: reserve notional + entry fees; close: return notional,
net P&L after exit fees only — entry fees were already reserved) so a
backtest's numbers are genuinely comparable to live paper performance, and
exposes state as the same `PortfolioState` shape
(packages/portfolio/state.py) so packages/risk's pure safety-belt/
position-sizing functions run completely unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from packages.portfolio.state import PortfolioState


@dataclass
class SimPosition:
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    size: float
    opened_at: datetime
    entry_fees: float = 0.0
    entry_slippage_bps: float = 0.0
    entry_regime: str | None = None


@dataclass
class SimTrade:
    direction: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    r_multiple: float | None
    outcome: str
    opened_at: datetime
    closed_at: datetime
    exit_reason: str
    entry_fees: float = 0.0
    exit_fees: float = 0.0
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0
    entry_regime: str | None = None


@dataclass
class EquityPoint:
    ts: datetime
    equity: float
    cash: float = 0.0
    exposure_pct: float = 0.0
    drawdown_pct: float = 0.0
    daily_pnl: float = 0.0


class SimulatedPortfolio:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.peak_equity = initial_capital
        self.equity_curve: list[EquityPoint] = []
        self._day_start_equity: dict = {}
        self._equity_history: list[tuple[datetime, float]] = []

    def _equity(self, open_position: SimPosition | None, current_price: float | None) -> float:
        if open_position is None or current_price is None:
            return self.cash
        direction_mult = 1 if open_position.direction == "long" else -1
        unrealized = (current_price - open_position.entry_price) * open_position.size * direction_mult
        notional = open_position.entry_price * open_position.size
        return self.cash + notional + unrealized

    def state(self, ts: datetime, open_position: SimPosition | None, current_price: float | None) -> PortfolioState:
        """The same PortfolioState shape live code reads — see module docstring."""
        equity = self._equity(open_position, current_price)
        self.peak_equity = max(self.peak_equity, equity)
        drawdown_pct = ((self.peak_equity - equity) / self.peak_equity * 100) if self.peak_equity > 0 else 0.0

        day_key = ts.date()
        equity_day_start = self._day_start_equity.setdefault(day_key, equity)
        daily_pnl = equity - equity_day_start
        daily_loss_pct = max(0.0, -daily_pnl) / equity_day_start * 100 if equity_day_start > 0 else 0.0

        week_cutoff = ts - timedelta(days=7)
        equity_week_start = equity
        for hist_ts, hist_equity in self._equity_history:
            if hist_ts > week_cutoff:
                break
            equity_week_start = hist_equity
        weekly_pnl = equity - equity_week_start
        weekly_loss_pct = max(0.0, -weekly_pnl) / equity_week_start * 100 if equity_week_start > 0 else 0.0

        month_cutoff = ts - timedelta(days=30)
        equity_month_start = equity
        for hist_ts, hist_equity in self._equity_history:
            if hist_ts > month_cutoff:
                break
            equity_month_start = hist_equity
        monthly_pnl = equity - equity_month_start
        monthly_loss_pct = max(0.0, -monthly_pnl) / equity_month_start * 100 if equity_month_start > 0 else 0.0

        exposure_notional = (open_position.entry_price * open_position.size) if open_position else 0.0
        exposure_pct = (exposure_notional / equity * 100) if equity > 0 else 0.0
        unrealized_pnl = equity - self.cash - exposure_notional

        return PortfolioState(
            ts=ts, cash=self.cash, equity=equity, exposure_pct=round(exposure_pct, 4),
            daily_pnl=round(daily_pnl, 2), daily_loss_pct=round(daily_loss_pct, 4),
            weekly_pnl=round(weekly_pnl, 2), weekly_loss_pct=round(weekly_loss_pct, 4),
            monthly_pnl=round(monthly_pnl, 2), monthly_loss_pct=round(monthly_loss_pct, 4),
            drawdown_pct=round(drawdown_pct, 4),
            unrealized_pnl=round(unrealized_pnl, 2), open_positions=[],
        )

    def record_equity(self, ts: datetime, open_position: SimPosition | None, current_price: float | None) -> None:
        state = self.state(ts, open_position, current_price)
        self.equity_curve.append(
            EquityPoint(
                ts=ts, equity=round(state.equity, 2), cash=round(self.cash, 2),
                exposure_pct=state.exposure_pct, drawdown_pct=state.drawdown_pct, daily_pnl=state.daily_pnl,
            )
        )
        self._equity_history.append((ts, state.equity))

    def open(
        self, *, direction: str, entry_price: float, stop_price: float, target_price: float | None, size: float,
        opened_at: datetime, entry_fees: float, entry_slippage_bps: float = 0.0, entry_regime: str | None = None,
    ) -> SimPosition:
        notional = entry_price * size
        self.cash -= notional + entry_fees
        return SimPosition(
            direction=direction, entry_price=entry_price, stop_price=stop_price, target_price=target_price,
            size=size, opened_at=opened_at, entry_fees=entry_fees, entry_slippage_bps=entry_slippage_bps,
            entry_regime=entry_regime,
        )

    def close(
        self, position: SimPosition, *, exit_price: float, closed_at: datetime, exit_reason: str,
        exit_fees: float, exit_slippage_bps: float = 0.0,
    ) -> SimTrade:
        direction_mult = 1 if position.direction == "long" else -1
        pnl = (exit_price - position.entry_price) * position.size * direction_mult - exit_fees
        stop_distance = abs(position.entry_price - position.stop_price)
        r_multiple = (pnl / (stop_distance * position.size)) if stop_distance > 0 else None
        outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")

        notional_returned = position.entry_price * position.size
        self.cash += notional_returned + pnl

        return SimTrade(
            direction=position.direction, entry_price=position.entry_price, exit_price=exit_price, size=position.size,
            pnl=round(pnl, 2), r_multiple=round(r_multiple, 4) if r_multiple is not None else None, outcome=outcome,
            opened_at=position.opened_at, closed_at=closed_at, exit_reason=exit_reason,
            entry_fees=round(position.entry_fees, 4), exit_fees=round(exit_fees, 4),
            entry_slippage_bps=position.entry_slippage_bps, exit_slippage_bps=exit_slippage_bps,
            entry_regime=position.entry_regime,
        )
