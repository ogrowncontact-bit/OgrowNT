"""Robustness Score — "PROMPT 7" §23. A single 0-100 number combining every
prior analysis this phase produces, weighted so no single lucky metric can
carry the score. §23's own list of what to consider is followed component
by component below; a component with no evidence available (e.g. walk-
forward optimization was never run) contributes **zero**, not a neutral
default -- an untested strategy is not "average," it's unproven, and a
"generous when data is missing" score would contradict every other honest-
default rule in this codebase.

Not a probability of profit (§23's own closing line, echoed in
packages/backtest/quality_score.py which builds on this score) -- it is a
relative measure of how much independent evidence supports the strategy
having a real, durable edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.backtest.stability import StabilityResult
from packages.backtest.walkforward_optimization import WalkForwardOptimizationResult

# Point budget, summing to 100 -- see module docstring for what each measures.
WEIGHT_OUT_OF_SAMPLE = 25
WEIGHT_PARAMETER_STABILITY = 15
WEIGHT_DRAWDOWN = 15
WEIGHT_CONSISTENCY = 15
WEIGHT_SAMPLE_SIZE = 10
WEIGHT_REGIME_DIVERSITY = 10
WEIGHT_ASSET_DIVERSITY = 5
WEIGHT_COST_SENSITIVITY = 5

TARGET_SAMPLE_SIZE = 30  # trades; full sample-size credit at or above this
ACCEPTABLE_DRAWDOWN_PCT = 15.0  # full drawdown credit at or below this
KNOWN_REGIMES = 8  # packages/quant/regime/classifier.py's regime vocabulary


@dataclass(frozen=True)
class RobustnessComponent:
    name: str
    score: float
    max_score: float
    evidence: str


@dataclass(frozen=True)
class RobustnessScoreResult:
    score: float
    components: list[RobustnessComponent] = field(default_factory=list)
    insufficient_evidence: list[str] = field(default_factory=list)


def _oos_component(wf: WalkForwardOptimizationResult | None) -> RobustnessComponent:
    if wf is None or wf.consistent is None:
        return RobustnessComponent("out_of_sample", 0, WEIGHT_OUT_OF_SAMPLE, "no walk-forward optimization result available")
    if not wf.consistent:
        return RobustnessComponent("out_of_sample", 0, WEIGHT_OUT_OF_SAMPLE, f"walk-forward optimization judged inconsistent: {wf.reason}")
    ratio = wf.oos_positive_window_ratio or 0.0
    return RobustnessComponent("out_of_sample", round(WEIGHT_OUT_OF_SAMPLE * ratio, 2), WEIGHT_OUT_OF_SAMPLE, wf.reason)


def _stability_component(stability: StabilityResult | None) -> RobustnessComponent:
    if stability is None or stability.stable is None:
        return RobustnessComponent("parameter_stability", 0, WEIGHT_PARAMETER_STABILITY, "no parameter stability check available")
    score = WEIGHT_PARAMETER_STABILITY if stability.stable else 0
    return RobustnessComponent("parameter_stability", score, WEIGHT_PARAMETER_STABILITY, stability.reason)


def _drawdown_component(max_drawdown_pct: float | None) -> RobustnessComponent:
    if max_drawdown_pct is None:
        return RobustnessComponent("drawdown", 0, WEIGHT_DRAWDOWN, "no drawdown data available")
    if max_drawdown_pct <= 0:
        return RobustnessComponent("drawdown", WEIGHT_DRAWDOWN, WEIGHT_DRAWDOWN, "no drawdown observed")
    ratio = min(1.0, ACCEPTABLE_DRAWDOWN_PCT / max_drawdown_pct)
    return RobustnessComponent("drawdown", round(WEIGHT_DRAWDOWN * ratio, 2), WEIGHT_DRAWDOWN, f"max_drawdown={max_drawdown_pct}%")


def _consistency_component(wf: WalkForwardOptimizationResult | None) -> RobustnessComponent:
    if wf is None or wf.oos_positive_window_ratio is None:
        return RobustnessComponent("consistency", 0, WEIGHT_CONSISTENCY, "no walk-forward window ratio available")
    ratio = wf.oos_positive_window_ratio
    return RobustnessComponent("consistency", round(WEIGHT_CONSISTENCY * ratio, 2), WEIGHT_CONSISTENCY, f"{ratio:.0%} of validation windows positive")


def _sample_size_component(num_trades: int) -> RobustnessComponent:
    ratio = min(1.0, num_trades / TARGET_SAMPLE_SIZE)
    return RobustnessComponent("sample_size", round(WEIGHT_SAMPLE_SIZE * ratio, 2), WEIGHT_SAMPLE_SIZE, f"{num_trades} trades (target {TARGET_SAMPLE_SIZE})")


def _regime_diversity_component(regime_breakdown: dict | None) -> RobustnessComponent:
    if not regime_breakdown:
        return RobustnessComponent("regime_diversity", 0, WEIGHT_REGIME_DIVERSITY, "no regime breakdown available")
    distinct = len([r for r in regime_breakdown if r != "unknown"])
    ratio = min(1.0, distinct / KNOWN_REGIMES)
    return RobustnessComponent("regime_diversity", round(WEIGHT_REGIME_DIVERSITY * ratio, 2), WEIGHT_REGIME_DIVERSITY, f"traded in {distinct}/{KNOWN_REGIMES} known regimes")


def _asset_diversity_component(asset_count: int) -> RobustnessComponent:
    ratio = min(1.0, max(0, asset_count - 1) / 2)  # full credit at 3+ assets tested
    return RobustnessComponent("asset_diversity", round(WEIGHT_ASSET_DIVERSITY * ratio, 2), WEIGHT_ASSET_DIVERSITY, f"tested on {asset_count} asset(s)")


def _cost_sensitivity_component(cost_survives: bool | None, slippage_survives: bool | None) -> RobustnessComponent:
    judged = [v for v in (cost_survives, slippage_survives) if v is not None]
    if not judged:
        return RobustnessComponent("cost_sensitivity", 0, WEIGHT_COST_SENSITIVITY, "no cost/slippage sensitivity data available")
    ratio = sum(1 for v in judged if v) / len(judged)
    return RobustnessComponent("cost_sensitivity", round(WEIGHT_COST_SENSITIVITY * ratio, 2), WEIGHT_COST_SENSITIVITY, f"survived {sum(1 for v in judged if v)}/{len(judged)} sensitivity sweeps")


def compute_robustness_score(
    *, walk_forward: WalkForwardOptimizationResult | None = None, stability: StabilityResult | None = None,
    max_drawdown_pct: float | None = None, num_trades: int = 0, regime_breakdown: dict | None = None,
    asset_count: int = 1, cost_sensitivity_survives: bool | None = None, slippage_sensitivity_survives: bool | None = None,
) -> RobustnessScoreResult:
    components = [
        _oos_component(walk_forward),
        _stability_component(stability),
        _drawdown_component(max_drawdown_pct),
        _consistency_component(walk_forward),
        _sample_size_component(num_trades),
        _regime_diversity_component(regime_breakdown),
        _asset_diversity_component(asset_count),
        _cost_sensitivity_component(cost_sensitivity_survives, slippage_sensitivity_survives),
    ]
    total = round(sum(c.score for c in components), 2)
    insufficient = [c.name for c in components if c.score == 0 and "no " in c.evidence and "available" in c.evidence]
    return RobustnessScoreResult(score=total, components=components, insufficient_evidence=insufficient)
