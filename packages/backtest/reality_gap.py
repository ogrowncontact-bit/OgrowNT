"""Reality Gap Analyzer — "PROMPT 7" §42. A structured comparison between a
strategy's reference backtest and its actual live (paper) performance,
queryable on demand — distinct from
packages/quant/learning/degradation.py's `check_degradation`, which only
ever answers "should an Alert fire right now" (a single expectancy-based
threshold check, cooldown-gated). This module answers the broader "how,
exactly, do backtest and reality differ" question §42 asks for, across
every metric both sides actually track.

`reference_backtest()` (the shared reference-backtest lookup) lives in
packages/quant/learning/degradation.py, not here: packages/backtest is
allowed to depend on packages/quant (docs/blueprint/01-repo-structure.md's
dependency table), the reverse isn't, so the one shared piece of logic has
to live on the quant side.

Return/expectancy units honestly don't line up 1:1: BacktestRun.net_return
is a % return on initial_capital, while StrategyPerformance has no
equivalent (it tracks P&L-shaped stats, not a return against a capital
base) — return_difference is reported as `None` with an explicit reason
rather than a fabricated proxy.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.quant.learning.degradation import reference_backtest
from packages.shared.models import StrategyPerformance, StrategyRow


@dataclass(frozen=True)
class RealityGapResult:
    strategy_id: int
    reference_backtest_id: int | None
    return_difference: float | None
    win_rate_difference: float | None
    expectancy_difference: float | None
    drawdown_difference: float | None
    execution_difference: float | None
    notes: list[str]


def _diff(live: float | None, backtest: float | None) -> float | None:
    if live is None or backtest is None:
        return None
    return round(live - backtest, 4)


def analyze_reality_gap(db: Session, strategy_id: int) -> RealityGapResult:
    strategy = db.get(StrategyRow, strategy_id)
    notes: list[str] = []
    if strategy is None:
        return RealityGapResult(strategy_id, None, None, None, None, None, None, ["strategy not found"])

    reference = reference_backtest(db, strategy_id)
    if reference is None:
        notes.append("no reference backtest on file -- run one via POST /api/backtests before comparing")
        return RealityGapResult(strategy_id, None, None, None, None, None, None, notes)

    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    if perf is None:
        notes.append("no live paper-trading performance recorded yet -- strategy hasn't closed a trade live")
        return RealityGapResult(strategy_id, reference.id, None, None, None, None, None, notes)

    notes.append("return_difference is NOT AVAILABLE: BacktestRun.net_return is a % return, StrategyPerformance tracks P&L-shaped stats with no equivalent return base")

    backtest_avg_win = (reference.extra_metrics or {}).get("avg_win")
    execution_difference = None
    if perf.avg_win is not None and backtest_avg_win is not None:
        execution_difference = _diff(perf.avg_win, backtest_avg_win)
    else:
        notes.append("execution_difference (avg_win proxy) NOT AVAILABLE: backtest has no extra_metrics.avg_win to compare against (older run, or no winning trades)")

    return RealityGapResult(
        strategy_id=strategy_id, reference_backtest_id=reference.id, return_difference=None,
        win_rate_difference=_diff(perf.win_rate, reference.win_rate),
        expectancy_difference=_diff(perf.expectancy, reference.expectancy),
        drawdown_difference=_diff(perf.max_drawdown, reference.max_drawdown),
        execution_difference=execution_difference, notes=notes,
    )
