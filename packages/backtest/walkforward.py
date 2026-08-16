"""Walk-forward validation — docs/blueprint/10-backtesting-paper-trading.md's
anti-overfitting technique #3: slide a fixed-size window across the
available history and check the strategy's edge holds up window over
window, not just in one lucky stretch.

Honest simplification: our four strategies (packages/quant/strategies) use
fixed, hand-set constants rather than a calibrated/fitted parameter set, so
there is no real "train" step to speak of yet — each window here is a
genuine held-out test window, and walk-forward is used for its
consistency-over-time value, not parameter re-fitting. A calibration step
would be a natural, separate future addition once there's a reason to fit
parameters rather than hand-set them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, run_backtest
from packages.quant.strategies.base import Strategy
from packages.risk.config import RiskLimits

# Below this many pooled trades across all windows, a consistency verdict
# would just be reading tea leaves — report "not enough data" rather than
# a confident-looking True/False.
MIN_TRADES_FOR_CONSISTENCY_VERDICT = 5


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    start_ts: datetime
    end_ts: datetime
    result: BacktestResult


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    consistent: bool | None  # None when there isn't enough data across windows to judge
    reason: str


def _verdict(windows: list[WalkForwardWindow]) -> WalkForwardResult:
    all_r_multiples = [t["r_multiple"] for w in windows for t in w.result.trades if t["r_multiple"] is not None]
    tradeable_windows = [w for w in windows if w.result.num_trades > 0]

    if len(all_r_multiples) < MIN_TRADES_FOR_CONSISTENCY_VERDICT:
        return WalkForwardResult(
            windows=windows, consistent=None,
            reason=(
                f"only {len(all_r_multiples)} total trades across {len(windows)} windows — "
                f"too few to judge consistency (need >= {MIN_TRADES_FOR_CONSISTENCY_VERDICT})"
            ),
        )

    pooled_expectancy = sum(all_r_multiples) / len(all_r_multiples)
    positive_windows = sum(1 for w in tradeable_windows if w.result.expectancy is not None and w.result.expectancy > 0)
    consistency_ratio = positive_windows / len(tradeable_windows) if tradeable_windows else 0.0

    # Not "every window must win" (too strict for small, noisy windows) --
    # the pooled edge must be real AND it must not be carried entirely by
    # one lucky window.
    consistent = pooled_expectancy > 0 and consistency_ratio >= 0.5
    reason = (
        f"pooled_expectancy={pooled_expectancy:.4f}R over {len(all_r_multiples)} trades, "
        f"{positive_windows}/{len(tradeable_windows)} tradeable windows had positive expectancy"
    )
    return WalkForwardResult(windows=windows, consistent=consistent, reason=reason)


def run_walk_forward(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, window_days: float, initial_capital: float,
    risk_limits: RiskLimits | None = None,
) -> WalkForwardResult:
    windows: list[WalkForwardWindow] = []
    window_delta = timedelta(days=window_days)
    cursor = start_ts
    index = 0
    while cursor < end_ts:
        window_end = min(cursor + window_delta, end_ts)
        result = run_backtest(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=cursor, end_ts=window_end, initial_capital=initial_capital, risk_limits=risk_limits,
        )
        windows.append(WalkForwardWindow(index=index, start_ts=cursor, end_ts=window_end, result=result))
        cursor = window_end
        index += 1

    return _verdict(windows)
