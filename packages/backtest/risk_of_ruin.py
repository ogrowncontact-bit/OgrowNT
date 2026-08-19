"""Risk of Ruin Analyzer — "PROMPT 7" §28. Estimates the probability that a
strategy's realized trade sequence, resampled, breaches a "ruin" threshold
(a drawdown level, or an absolute capital-loss level) rather than deriving
it from a closed-form formula.

§28 explicitly says "utilizar modelos adequados e documentar as hipóteses" —
the assumptions here, stated plainly:
- Trades are resampled independently (bootstrap) from the reference
  backtest's own closed trades — i.e. future trades are assumed to be
  drawn from the same distribution as past ones. No regime persistence,
  no serial correlation between consecutive trades is modeled.
- "Ruin" is user-defined (a drawdown_pct threshold and/or a capital-loss
  threshold), not assumed to be total capital loss.
- The simulation horizon is exactly `len(trades)` trades per simulation —
  the same number the reference backtest actually produced, not an
  arbitrarily longer or shorter simulated career.

This deliberately reuses packages/backtest/monte_carlo.py's `bootstrap`
resampling rather than reimplementing a parallel simulator — risk of ruin
IS a Monte Carlo question (§28 sits right after the Monte Carlo section for
exactly this reason), just asked with a specific pass/fail threshold instead
of a percentile table.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from packages.backtest.monte_carlo import DEFAULT_NUM_SIMULATIONS, simulate_one_run


@dataclass(frozen=True)
class RiskOfRuinResult:
    probability_of_ruin: float | None
    drawdown_threshold_pct: float | None
    capital_loss_threshold_pct: float | None
    num_simulations: int
    random_seed: int
    assumptions: list[str]


ASSUMPTIONS = [
    "trades are resampled independently (bootstrap) from the reference backtest's closed trades",
    "no serial correlation or regime persistence between consecutive trades is modeled",
    "simulation horizon equals the reference backtest's own trade count, not a longer simulated career",
    "this is a simulation-based estimate over past trades, not a probabilistic guarantee about future performance",
]


def estimate_risk_of_ruin(
    trades: list[dict], *, initial_capital: float, drawdown_threshold_pct: float | None = None,
    capital_loss_threshold_pct: float | None = None, num_simulations: int = DEFAULT_NUM_SIMULATIONS, random_seed: int = 42,
) -> RiskOfRuinResult:
    if drawdown_threshold_pct is None and capital_loss_threshold_pct is None:
        raise ValueError("at least one of drawdown_threshold_pct or capital_loss_threshold_pct must be set")
    if not trades:
        return RiskOfRuinResult(
            probability_of_ruin=None, drawdown_threshold_pct=drawdown_threshold_pct,
            capital_loss_threshold_pct=capital_loss_threshold_pct, num_simulations=0, random_seed=random_seed,
            assumptions=[*ASSUMPTIONS, "no closed trades in the reference backtest -- nothing to resample"],
        )

    rng = random.Random(random_seed)
    ruin_count = 0
    for _ in range(num_simulations):
        run = simulate_one_run(rng, trades, initial_capital, "bootstrap")
        hit_drawdown = drawdown_threshold_pct is not None and run.max_drawdown_pct >= drawdown_threshold_pct
        loss_pct = max(0.0, (initial_capital - run.final_equity) / initial_capital * 100) if initial_capital > 0 else 0.0
        hit_capital_loss = capital_loss_threshold_pct is not None and loss_pct >= capital_loss_threshold_pct
        if hit_drawdown or hit_capital_loss:
            ruin_count += 1

    return RiskOfRuinResult(
        probability_of_ruin=round(ruin_count / num_simulations, 4),
        drawdown_threshold_pct=drawdown_threshold_pct, capital_loss_threshold_pct=capital_loss_threshold_pct,
        num_simulations=num_simulations, random_seed=random_seed, assumptions=ASSUMPTIONS,
    )
