"""Monte Carlo Engine — "PROMPT 7" §24-28. Resamples a reference backtest's
*closed trades* (never raw price data — see module docstring rationale
below) to build a distribution of plausible alternate outcomes, not a
single point estimate.

Every method draws from the same `random.Random(random_seed)` instance in
run order, so the same seed always reproduces the exact same simulation
batch (§49). "Recovery duration" is measured in trades-elapsed, not
calendar time: a resampled/shuffled sequence has no real timestamps to
recover a duration *in* — reported honestly as `recovery_duration_trades`,
not disguised as a time unit it isn't.

§27's own reminder is worth repeating in code, not just prose: none of this
is a prediction. "95th percentile drawdown: 18.4%" describes the simulated
distribution *of this specific resampling of past trades*, not a forecast.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

METHODS = ("trade_reshuffling", "bootstrap", "return_perturbation", "slippage_perturbation", "execution_perturbation")

DEFAULT_NUM_SIMULATIONS = 1000
# Perturbation magnitudes -- documented assumptions, not fitted to any
# specific venue: return_perturbation jitters each trade's P&L by
# +/-RETURN_PERTURBATION_STDEV (relative, normally distributed);
# slippage_perturbation subtracts an extra 0-SLIPPAGE_PERTURBATION_MAX_PCT
# of trade notional; execution_perturbation zeroes out a trade with
# probability EXECUTION_MISS_PROBABILITY (a "missed fill").
RETURN_PERTURBATION_STDEV = 0.15
SLIPPAGE_PERTURBATION_MAX_PCT = 0.003
EXECUTION_MISS_PROBABILITY = 0.05

PERCENTILE_POINTS = (5, 10, 25, 50, 75, 90, 95)


@dataclass(frozen=True)
class SimulationRun:
    final_equity: float
    return_pct: float
    max_drawdown_pct: float
    losing_streak: int
    recovered: bool
    recovery_duration_trades: int | None


def _percentiles(values: list[float]) -> dict:
    if not values:
        return dict.fromkeys((f"p{p}" for p in PERCENTILE_POINTS), None)
    ordered = sorted(values)
    result = {}
    for p in PERCENTILE_POINTS:
        result[f"p{p}"] = round(statistics.quantiles(ordered, n=100, method="inclusive")[p - 1], 4) if len(ordered) >= 2 else round(ordered[0], 4)
    return result


def _resample_pnls(rng: random.Random, trades: list[dict], method: str) -> list[float]:
    pnls = [t["pnl"] for t in trades]

    if method == "trade_reshuffling":
        shuffled = list(pnls)
        rng.shuffle(shuffled)
        return shuffled

    if method == "bootstrap":
        return [rng.choice(pnls) for _ in pnls]

    if method == "return_perturbation":
        # Scale each trade's P&L magnitude by a random factor centered on 1.0
        # -- sign is never flipped (that would model a different trade
        # outcome entirely, not uncertainty in *this* trade's realized size).
        return [p * max(0.0, rng.gauss(1.0, RETURN_PERTURBATION_STDEV)) for p in pnls]

    if method == "slippage_perturbation":
        result = []
        for t in trades:
            notional = abs(t["entry_price"] * t["size"])
            extra_cost = notional * rng.uniform(0.0, SLIPPAGE_PERTURBATION_MAX_PCT)
            result.append(t["pnl"] - extra_cost)
        return result

    if method == "execution_perturbation":
        return [0.0 if rng.random() < EXECUTION_MISS_PROBABILITY else p for p in pnls]

    raise ValueError(f"unknown Monte Carlo method: {method!r} (expected one of {METHODS})")


def simulate_one_run(rng: random.Random, trades: list[dict], initial_capital: float, method: str) -> SimulationRun:
    pnls = _resample_pnls(rng, trades, method)

    equity = initial_capital
    peak = initial_capital
    max_dd_pct = 0.0
    current_losing_streak = 0
    max_losing_streak = 0
    peak_index = 0
    recovered = False
    recovery_duration: int | None = None
    underwater_since: int | None = None

    for i, pnl in enumerate(pnls):
        equity += pnl
        current_losing_streak = current_losing_streak + 1 if pnl < 0 else 0
        max_losing_streak = max(max_losing_streak, current_losing_streak)

        if equity >= peak:
            if underwater_since is not None:
                recovered = True
                recovery_duration = i - peak_index
            peak = equity
            peak_index = i
            underwater_since = None
        else:
            if underwater_since is None:
                underwater_since = i
            if peak > 0:
                max_dd_pct = max(max_dd_pct, (peak - equity) / peak * 100)

    return_pct = (equity - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0.0
    return SimulationRun(
        final_equity=round(equity, 2), return_pct=round(return_pct, 4), max_drawdown_pct=round(max_dd_pct, 4),
        losing_streak=max_losing_streak, recovered=recovered, recovery_duration_trades=recovery_duration,
    )


@dataclass(frozen=True)
class MonteCarloOutput:
    method: str
    num_simulations: int
    random_seed: int
    percentiles: dict = field(default_factory=dict)
    probability_of_loss: float = 0.0
    probability_of_drawdown_threshold: float | None = None
    drawdown_threshold_pct: float | None = None
    notes: dict = field(default_factory=dict)


def run_monte_carlo(
    trades: list[dict], *, initial_capital: float, method: str = "trade_reshuffling",
    num_simulations: int = DEFAULT_NUM_SIMULATIONS, random_seed: int = 42, drawdown_threshold_pct: float | None = None,
) -> MonteCarloOutput:
    if method not in METHODS:
        raise ValueError(f"unknown Monte Carlo method: {method!r} (expected one of {METHODS})")
    if not trades:
        return MonteCarloOutput(
            method=method, num_simulations=0, random_seed=random_seed,
            notes={"reason": "no closed trades in the reference backtest -- nothing to resample"},
        )

    rng = random.Random(random_seed)
    runs = [simulate_one_run(rng, trades, initial_capital, method) for _ in range(num_simulations)]

    final_equities = [r.final_equity for r in runs]
    returns = [r.return_pct for r in runs]
    drawdowns = [r.max_drawdown_pct for r in runs]
    losing_streaks = [float(r.losing_streak) for r in runs]
    recovery_durations = [float(r.recovery_duration_trades) for r in runs if r.recovery_duration_trades is not None]

    probability_of_loss = round(sum(1 for e in final_equities if e < initial_capital) / len(runs), 4)
    probability_of_drawdown = None
    if drawdown_threshold_pct is not None:
        probability_of_drawdown = round(sum(1 for d in drawdowns if d >= drawdown_threshold_pct) / len(runs), 4)

    return MonteCarloOutput(
        method=method, num_simulations=num_simulations, random_seed=random_seed,
        percentiles={
            "final_equity": _percentiles(final_equities),
            "return_pct": _percentiles(returns),
            "max_drawdown_pct": _percentiles(drawdowns),
            "losing_streak": _percentiles(losing_streaks),
            "recovery_duration_trades": _percentiles(recovery_durations) if recovery_durations else None,
        },
        probability_of_loss=probability_of_loss,
        probability_of_drawdown_threshold=probability_of_drawdown,
        drawdown_threshold_pct=drawdown_threshold_pct,
        notes={"trades_resampled": len(trades), "recovered_simulations": sum(1 for r in runs if r.recovered)},
    )
