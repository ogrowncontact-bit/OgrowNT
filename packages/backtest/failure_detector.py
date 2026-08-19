"""Strategy Failure Detector — "PROMPT 7" §43. Consolidates every signal
this phase's modules can produce into one of three verdicts. Advisory only:
returns a verdict and reasons, never mutates `strategies.lifecycle_stage`
itself -- the same "DET proposes, a human/existing automatic mechanism
decides" split as packages/quant/learning/promotion.py (human-gated
promotion) and packages/quant/learning/quarantine.py (already-automatic,
but keyed off *live* health score, not backtest-time evidence).

Two verdict levels, split by what kind of evidence triggers them:
- STRATEGY_REJECTED: backtest-time evidence the strategy never had a real
  edge to begin with (negative expectancy, poor Monte Carlo, failed cost
  sensitivity, REJECTED quality status).
- STRATEGY_QUARANTINED: live evidence an edge that *did* exist has
  degraded (a Reality Gap big enough to matter, or a DEGRADED quality
  status) -- this only makes sense once there's live performance to
  compare against a backtest, which is why it's a separate branch rather
  than folded into REJECTED's checks.

A verdict of "OK" is never returned as a claim the strategy is safe or will
be profitable -- see packages/backtest/quality_score.py's own equivalent
disclaimer; this module only ever says whether known failure evidence was
found, not whether none exists to find.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.backtest.quality_score import DEGRADED, REJECTED
from packages.backtest.reality_gap import RealityGapResult

STRATEGY_OK = "STRATEGY_OK"
STRATEGY_REJECTED = "STRATEGY_REJECTED"
STRATEGY_QUARANTINED = "STRATEGY_QUARANTINED"

DEFAULT_PROBABILITY_OF_LOSS_THRESHOLD = 0.5
# A Reality Gap this large (in R-multiples of expectancy) is treated as
# meaningful degradation, not routine live noise around the backtest number.
DEGRADATION_EXPECTANCY_GAP_THRESHOLD = -0.15


@dataclass(frozen=True)
class FailureVerdict:
    verdict: str
    reasons: list[str] = field(default_factory=list)


def detect_strategy_failure(
    *, expectancy: float | None = None, max_drawdown_pct: float | None = None, max_drawdown_limit_pct: float | None = None,
    quality_status: str | None = None, reality_gap: RealityGapResult | None = None,
    monte_carlo_probability_of_loss: float | None = None,
    probability_of_loss_threshold: float = DEFAULT_PROBABILITY_OF_LOSS_THRESHOLD,
    cost_sensitivity_survives: bool | None = None, slippage_sensitivity_survives: bool | None = None,
) -> FailureVerdict:
    rejection_reasons: list[str] = []

    if expectancy is not None and expectancy <= 0:
        rejection_reasons.append(f"negative or zero expectancy: {expectancy}R")
    if max_drawdown_pct is not None and max_drawdown_limit_pct is not None and max_drawdown_pct > max_drawdown_limit_pct:
        rejection_reasons.append(f"max_drawdown {max_drawdown_pct}% exceeds the {max_drawdown_limit_pct}% limit")
    if quality_status == REJECTED:
        rejection_reasons.append("Strategy Quality Score classified the strategy REJECTED")
    if monte_carlo_probability_of_loss is not None and monte_carlo_probability_of_loss > probability_of_loss_threshold:
        rejection_reasons.append(f"Monte Carlo probability_of_loss {monte_carlo_probability_of_loss} exceeds {probability_of_loss_threshold}")
    if cost_sensitivity_survives is False:
        rejection_reasons.append("did not survive the cost sensitivity sweep")
    if slippage_sensitivity_survives is False:
        rejection_reasons.append("did not survive the slippage sensitivity sweep")

    if rejection_reasons:
        return FailureVerdict(STRATEGY_REJECTED, rejection_reasons)

    quarantine_reasons: list[str] = []
    if quality_status == DEGRADED:
        quarantine_reasons.append("Strategy Quality Score classified the strategy DEGRADED")
    if reality_gap is not None and reality_gap.expectancy_difference is not None and reality_gap.expectancy_difference <= DEGRADATION_EXPECTANCY_GAP_THRESHOLD:
        quarantine_reasons.append(f"live expectancy is {reality_gap.expectancy_difference}R below the reference backtest -- Reality Gap threshold {DEGRADATION_EXPECTANCY_GAP_THRESHOLD}R")

    if quarantine_reasons:
        return FailureVerdict(STRATEGY_QUARANTINED, quarantine_reasons)

    return FailureVerdict(STRATEGY_OK, [])
