"""Builds ScoringInputs from a strategy's read of the market — the bridge
between the Strategy Engine (Phase 2) and the Opportunity Scoring Engine
(docs/blueprint/07-scoring-engine.md).

Several inputs the full formula calls for don't exist as real signals yet:
Pattern Engine and News Intelligence are Phase 4, Learning/Strategy Memory
(historical edge, strategy performance) is Phase 5, and Portfolio/Risk
Engine (correlation, execution cost, drawdown) is Phase 3. Per
docs/blueprint/00-overview.md's "no hallucinated data" rule, those are
reported as an explicit neutral 50 (or 0 for penalties that literally
cannot fire yet), never a fabricated real-looking number — every score
generated in Phase 2 is muted accordingly, which is the honest behavior.
"""
from __future__ import annotations

from packages.quant.regime.classifier import REGIME_HIGH_VOLATILITY
from packages.quant.scoring.engine import ScoringInputs
from packages.quant.strategies.base import AnalysisResult, MarketContext, Strategy, StrategySignal

PHASE2_NEUTRAL_DEFAULTS = ("pattern", "historical_edge", "news", "strategy_performance")
TARGET_RISK_REWARD_FOR_FULL_SCORE = 3.0


def _liquidity_proxy(ctx: MarketContext) -> float:
    """Volume-relative-to-average as a stand-in for real orderbook depth
    (docs/blueprint/08-risk-engine.md's spread/depth checks arrive Phase 3).
    """
    avg_vol = ctx.indicators.avg_volume_20
    current_vol = ctx.candles[-1].volume
    if not avg_vol:
        return 50.0
    return max(0.0, min(100.0, (current_vol / avg_vol) * 50))


def _volatility_penalty_fraction(ctx: MarketContext) -> float:
    if ctx.regime.regime == REGIME_HIGH_VOLATILITY:
        return min(1.0, ctx.regime.confidence)
    return 0.0


def build_scoring_inputs(
    ctx: MarketContext, strategy: Strategy, analysis: AnalysisResult, signal: StrategySignal
) -> ScoringInputs:
    technical = round(analysis.strength * 100, 2)
    regime_fit = round(strategy.regime_fit(ctx.regime.regime) * 100, 2)
    risk_reward_score = round(min(100.0, (signal.risk_reward / TARGET_RISK_REWARD_FOR_FULL_SCORE) * 100), 2)
    liquidity = round(_liquidity_proxy(ctx), 2)

    return ScoringInputs(
        technical=technical,
        pattern=50.0,
        regime_fit=regime_fit,
        historical_edge=50.0,
        liquidity=liquidity,
        news=50.0,
        risk_reward=risk_reward_score,
        strategy_performance=50.0,
        volatility_penalty=_volatility_penalty_fraction(ctx),
        correlation_penalty=0.0,
        execution_cost_penalty=0.0,
        drawdown_penalty=0.0,
        notes={"phase2_neutral_defaults": PHASE2_NEUTRAL_DEFAULTS},
    )
