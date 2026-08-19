"""Stress Testing Engine — "PROMPT 7" §29-30, §60. Each scenario re-runs the
same strategy/asset/window through packages/backtest/engine.py with one
input deliberately made harsher than the base case, then reports the delta
against a reference run. Every scenario is a *real* re-run of the engine
(same event loop, same Risk Engine, same no-look-ahead guarantees) with a
concrete, mechanical change — never a hand-waved "assume 20% worse" applied
after the fact.

Scenario -> mechanism:
  volatility_spike       ATR-scaled slippage (VOLATILITY_BASED SlippageModel)
                         at a higher base bps than normal
  liquidity_reduction    a higher base bps on the existing LIQUIDITY_BASED
                         qty/volume-ratio slippage model -- same real-world
                         effect as thinner order books, expressed through
                         the cost model rather than mutating volume data
  spread_expansion       spread_bps multiplied by a factor
  slippage_increase      a flat PERCENTAGE SlippageModel at a higher bps
  gap                    a single synthetic large adverse jump inserted into
                         the candle series at the window's midpoint
  regime_reversal        the second half of the window's candles reversed in
                         direction (uptrend -> downtrend) via price mirroring
  market_crash           a sustained sharp decline replacing the window's
                         final bars, large enough to test kill-switch
                         behavior (§60)

Two scenarios §29 names are deliberately not implemented, with reasons
rather than a silent gap:
  consecutive_losses     already covered, with a real statistical
                         distribution rather than one hand-picked stretch,
                         by packages/backtest/monte_carlo.py's
                         `losing_streak` percentiles over the same reference
                         trades -- a second, cruder mechanism here would add
                         complexity without adding evidence.
  news_shock             would require injecting a synthetic NewsEvent/
                         NewsImpact into the database for
                         packages/backtest/news_replay.py to read back --
                         exactly the kind of write to a table other live
                         cadences (News Intelligence worker, dashboard)
                         read concurrently that gap/regime_reversal/
                         market_crash deliberately avoid by staying in
                         memory (see below). Not worth compromising that
                         invariant for one scenario; a future in-memory
                         news-signal override on run_backtest_on_candles
                         could add it safely.

Kill Switch drill (§60) rides on `market_crash`: packages/backtest/risk.py's
evaluate_signal_for_backtest already calls should_trigger_kill_switch on
every candidate signal, so a severe enough synthetic crash exercises the
exact same code path a real live drawdown would. "Logs generated" (§60) is
satisfied by `extra_metrics.risk_veto_counts["kill_switch"]`
(packages/backtest/engine.py) on the crash run -- a genuine count of how
many times the kill switch actually fired, not a claim taken on faith.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, _load_candles, run_backtest, run_backtest_on_candles
from packages.backtest.execution_models import ExecutionConfig, SlippageModel
from packages.backtest.stress_data import CRASH_TAIL_BARS, DEFAULT_CRASH_DROP_PCT, DEFAULT_GAP_PCT, apply_gap, apply_market_crash, apply_regime_reversal
from packages.quant.strategies.base import Strategy
from packages.risk.config import RiskLimits

SCENARIOS = (
    "volatility_spike", "liquidity_reduction", "spread_expansion", "slippage_increase",
    "gap", "regime_reversal", "market_crash",
)

DEFAULT_VOLATILITY_MULTIPLIER = 3.0
DEFAULT_LIQUIDITY_REDUCTION_FACTOR = 5.0
DEFAULT_SPREAD_MULTIPLIER = 4.0
DEFAULT_SLIPPAGE_MULTIPLIER = 5.0


@dataclass(frozen=True)
class StressScenarioResult:
    scenario: str
    params: dict
    baseline: BacktestResult
    stressed: BacktestResult
    return_delta: float | None
    drawdown_delta: float | None
    survived: bool | None  # None when neither run produced a judgeable net_return
    notes: dict = field(default_factory=dict)


def _survived(baseline: BacktestResult, stressed: BacktestResult) -> tuple[bool | None, float | None, float | None]:
    if baseline.net_return is None or stressed.net_return is None:
        return None, None, None
    return_delta = round(stressed.net_return - baseline.net_return, 4)
    drawdown_delta = None
    if baseline.max_drawdown is not None and stressed.max_drawdown is not None:
        drawdown_delta = round(stressed.max_drawdown - baseline.max_drawdown, 4)
    return stressed.net_return > 0, return_delta, drawdown_delta


def _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits, execution=None) -> BacktestResult:
    return run_backtest(
        db, strategy=strategy_factory(), asset_id=asset_id, symbol=symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits, execution=execution,
    )


def run_stress_scenario(
    db: Session, *, scenario: str, strategy_factory: Callable[[], Strategy], asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
    params: dict | None = None,
) -> StressScenarioResult:
    """`strategy_factory` is a zero-arg callable (e.g. `lambda: BreakoutStrategy()`)
    since each of baseline and stressed run needs its own fresh strategy
    instance (some strategies carry no mutable state, but nothing here
    should assume that)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown stress scenario: {scenario!r} (expected one of {SCENARIOS})")
    params = params or {}

    baseline = _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits)

    if scenario == "volatility_spike":
        multiplier = params.get("multiplier", DEFAULT_VOLATILITY_MULTIPLIER)
        execution = ExecutionConfig(slippage_model=SlippageModel(kind="volatility_based", slippage_bps=2.0 * multiplier))
        stressed = _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits, execution)
        used_params = {"multiplier": multiplier}

    elif scenario == "liquidity_reduction":
        factor = params.get("factor", DEFAULT_LIQUIDITY_REDUCTION_FACTOR)
        execution = ExecutionConfig(slippage_model=SlippageModel(kind="liquidity_based", slippage_bps=2.0 * factor))
        stressed = _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits, execution)
        used_params = {"factor": factor}

    elif scenario == "spread_expansion":
        multiplier = params.get("multiplier", DEFAULT_SPREAD_MULTIPLIER)
        execution = ExecutionConfig(spread_bps=5.0 * multiplier)
        stressed = _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits, execution)
        used_params = {"multiplier": multiplier}

    elif scenario == "slippage_increase":
        multiplier = params.get("multiplier", DEFAULT_SLIPPAGE_MULTIPLIER)
        execution = ExecutionConfig(slippage_model=SlippageModel(kind="percentage", slippage_bps=2.0 * multiplier))
        stressed = _run(db, strategy_factory, asset_id, symbol, timeframe, start_ts, end_ts, initial_capital, risk_limits, execution)
        used_params = {"multiplier": multiplier}

    elif scenario in ("gap", "regime_reversal", "market_crash"):
        # Real candles, loaded read-only, transformed entirely in memory --
        # never written back to `ohlcv` (see stress_test.py's module
        # docstring and stress_data.py for why).
        real_candles = _load_candles(db, asset_id, timeframe, start_ts, end_ts)
        if scenario == "gap":
            shocked_candles, used_params = apply_gap(real_candles, params.get("gap_pct", DEFAULT_GAP_PCT))
        elif scenario == "regime_reversal":
            shocked_candles, used_params = apply_regime_reversal(real_candles)
        else:
            shocked_candles, used_params = apply_market_crash(
                real_candles, params.get("drop_pct", DEFAULT_CRASH_DROP_PCT), int(params.get("tail_bars", CRASH_TAIL_BARS))
            )
        stressed = run_backtest_on_candles(
            db, strategy=strategy_factory(), asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            candles=shocked_candles, initial_capital=initial_capital, risk_limits=risk_limits,
        )

    else:  # pragma: no cover -- guarded by the SCENARIOS membership check above
        raise ValueError(scenario)

    survived, return_delta, drawdown_delta = _survived(baseline, stressed)
    notes: dict = {}
    if scenario == "market_crash":
        notes["kill_switch_fired"] = stressed.extra_metrics.get("risk_veto_counts", {}).get("kill_switch", 0) > 0
        notes["kill_switch_trigger_count"] = stressed.extra_metrics.get("risk_veto_counts", {}).get("kill_switch", 0)
        notes["equity_curve_tracked_through_crash"] = len(stressed.equity_curve) > 0

    return StressScenarioResult(
        scenario=scenario, params=used_params, baseline=baseline, stressed=stressed,
        return_delta=return_delta, drawdown_delta=drawdown_delta, survived=survived, notes=notes,
    )
