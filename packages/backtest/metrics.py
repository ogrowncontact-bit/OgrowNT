"""Enriched backtest metrics — "PROMPT 7" §11-15, 31: everything beyond the
Phase 6 core set (net/CAGR return, win rate, profit factor, max drawdown,
avg trade, expectancy, Sharpe-like — still computed in
packages/backtest/engine.py's `_summarize`). Pure functions over the same
`SimTrade`/`EquityPoint` lists the engine already produces; nothing here
touches the event loop or introduces new data sources, so it can't
introduce look-ahead bias.

Every metric that isn't statistically meaningful for the run at hand
(fewer than two trades for a std-dev-based figure, no losing trades for a
loss-based figure, etc.) reports `None` rather than a misleading number —
callers/serializers render that as "NOT AVAILABLE" per §11's own rule.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from packages.backtest.portfolio import EquityPoint, SimTrade

TRADING_DAYS_UNAVAILABLE = "NOT AVAILABLE"


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _stats(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "median": None, "min": None, "max": None, "stdev": None}
    return {
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "stdev": round(statistics.pstdev(values), 4) if len(values) >= 2 else None,
    }


def gross_pnl(trades: list[SimTrade]) -> dict:
    wins = [t.pnl for t in trades if t.outcome == "win"]
    losses = [t.pnl for t in trades if t.outcome == "loss"]
    return {
        "gross_profit": round(sum(wins), 2) if wins else 0.0,
        "gross_loss": round(sum(losses), 2) if losses else 0.0,
        "avg_win": _avg(wins),
        "avg_loss": _avg(losses),
        "largest_win": round(max(wins), 2) if wins else None,
        "largest_loss": round(min(losses), 2) if losses else None,
    }


def sortino_ratio(r_multiples: list[float]) -> float | None:
    """Same units/spirit as engine.py's `_sharpe` (per-trade R-multiples,
    not a daily-return series -- honest given the engine has no fixed bar
    cadence to annualize against), but penalizing only downside variance."""
    if len(r_multiples) < 2:
        return None
    mean_r = sum(r_multiples) / len(r_multiples)
    downside = [min(0.0, r) ** 2 for r in r_multiples]
    downside_variance = sum(downside) / len(r_multiples)
    downside_dev = math.sqrt(downside_variance)
    return round(mean_r / downside_dev, 4) if downside_dev > 0 else None


def recovery_factor(net_pnl: float, max_drawdown_amount: float | None) -> float | None:
    if not max_drawdown_amount or max_drawdown_amount <= 0:
        return None
    return round(net_pnl / max_drawdown_amount, 4)


def exposure_and_turnover(equity_curve: list[EquityPoint], trades: list[SimTrade], initial_capital: float) -> dict:
    exposure_values = [p.exposure_pct for p in equity_curve]
    avg_exposure_pct = round(sum(exposure_values) / len(exposure_values), 4) if exposure_values else None
    traded_notional = sum(t.entry_price * t.size + t.exit_price * t.size for t in trades)
    turnover = round(traded_notional / initial_capital, 4) if initial_capital > 0 else None
    return {"avg_exposure_pct": avg_exposure_pct, "turnover": turnover}


def drawdown_detail(equity_curve: list[EquityPoint]) -> dict:
    """Underwater-period analysis beyond engine.py's single max_drawdown
    scalar: how long the run spent underwater on average, the longest
    single stretch, and whether it ever recovered to a new peak."""
    if len(equity_curve) < 2:
        return {"average_drawdown_pct": None, "max_drawdown_duration_bars": None, "recovery_duration_bars": None, "still_underwater": None}

    peak = equity_curve[0].equity
    peak_index = 0
    underwater_pcts: list[float] = []
    durations: list[int] = []
    recovery_durations: list[int] = []
    underwater_start: int | None = None

    for i, point in enumerate(equity_curve):
        if point.equity >= peak:
            if underwater_start is not None:
                durations.append(i - underwater_start)
                recovery_durations.append(i - peak_index)
                underwater_start = None
            peak = point.equity
            peak_index = i
        else:
            if underwater_start is None:
                underwater_start = i
            underwater_pcts.append((peak - point.equity) / peak * 100 if peak > 0 else 0.0)

    still_underwater = underwater_start is not None
    if still_underwater:
        durations.append(len(equity_curve) - 1 - underwater_start)  # type: ignore[operator]

    return {
        "average_drawdown_pct": round(sum(underwater_pcts) / len(underwater_pcts), 4) if underwater_pcts else 0.0,
        "max_drawdown_duration_bars": max(durations) if durations else 0,
        "recovery_duration_bars": max(recovery_durations) if recovery_durations else None,
        "still_underwater": still_underwater,
    }


def streaks(trades: list[SimTrade]) -> dict:
    """Max/avg consecutive winning and losing streaks, in trade-close order
    (§15). Breakeven trades break a streak without extending either side."""
    if not trades:
        return {"max_winning_streak": 0, "max_losing_streak": 0, "avg_winning_streak": None, "avg_losing_streak": None}

    ordered = sorted(trades, key=lambda t: t.closed_at)
    win_runs: list[int] = []
    loss_runs: list[int] = []
    current_outcome: str | None = None
    current_len = 0

    for t in ordered:
        if t.outcome == current_outcome and t.outcome in ("win", "loss"):
            current_len += 1
        else:
            if current_outcome == "win":
                win_runs.append(current_len)
            elif current_outcome == "loss":
                loss_runs.append(current_len)
            current_outcome = t.outcome if t.outcome in ("win", "loss") else None
            current_len = 1 if current_outcome else 0

    if current_outcome == "win":
        win_runs.append(current_len)
    elif current_outcome == "loss":
        loss_runs.append(current_len)

    return {
        "max_winning_streak": max(win_runs) if win_runs else 0,
        "max_losing_streak": max(loss_runs) if loss_runs else 0,
        "avg_winning_streak": _avg([float(x) for x in win_runs]),
        "avg_losing_streak": _avg([float(x) for x in loss_runs]),
    }


def trade_distribution(trades: list[SimTrade]) -> dict:
    """Summary statistics (not raw per-trade lists -- those already live in
    BacktestResult.trades) for returns, holding time, risk/reward realized,
    slippage and fees, per §14."""
    returns = [t.pnl for t in trades]
    holding_hours = [(t.closed_at - t.opened_at).total_seconds() / 3600 for t in trades]
    risk_rewards = [t.r_multiple for t in trades if t.r_multiple is not None]
    slippage_bps = [t.entry_slippage_bps for t in trades] + [t.exit_slippage_bps for t in trades]
    fees = [t.entry_fees + t.exit_fees for t in trades]

    return {
        "returns": _stats(returns),
        "holding_time_hours": _stats(holding_hours),
        "risk_reward_realized": _stats(risk_rewards),
        "slippage_bps": _stats(slippage_bps),
        "fees": _stats(fees),
    }


def regime_breakdown(trades: list[SimTrade]) -> dict:
    """Performance segmented by the regime active at trade entry — §31.
    A trade with no recorded entry_regime (older/legacy data) is grouped
    under 'unknown' rather than silently dropped."""
    by_regime: dict[str, list[SimTrade]] = {}
    for t in trades:
        key = t.entry_regime or "unknown"
        by_regime.setdefault(key, []).append(t)

    result: dict[str, dict] = {}
    for regime, regime_trades in by_regime.items():
        r_multiples = [t.r_multiple for t in regime_trades if t.r_multiple is not None]
        wins = [t for t in regime_trades if t.outcome == "win"]
        result[regime] = {
            "num_trades": len(regime_trades),
            "win_rate": round(len(wins) / len(regime_trades), 4) if regime_trades else None,
            "expectancy": round(sum(r_multiples) / len(r_multiples), 4) if r_multiples else None,
            "net_pnl": round(sum(t.pnl for t in regime_trades), 2),
        }
    return result


@dataclass(frozen=True)
class ExtraMetrics:
    as_dict: dict


def compute_extra_metrics(
    *, equity_curve: list[EquityPoint], trades: list[SimTrade], initial_capital: float,
    net_pnl: float, max_drawdown_pct: float | None, r_multiples: list[float],
) -> dict:
    peak_equity = max((p.equity for p in equity_curve), default=initial_capital)
    max_drawdown_amount = (max_drawdown_pct / 100 * peak_equity) if max_drawdown_pct else None

    return {
        **gross_pnl(trades),
        "sortino_ratio": sortino_ratio(r_multiples),
        "recovery_factor": recovery_factor(net_pnl, max_drawdown_amount),
        **exposure_and_turnover(equity_curve, trades, initial_capital),
        "drawdown_detail": drawdown_detail(equity_curve),
        "streaks": streaks(trades),
        "trade_distribution": trade_distribution(trades),
        "regime_breakdown": regime_breakdown(trades),
        "total_fees": round(sum(t.entry_fees + t.exit_fees for t in trades), 4),
    }
