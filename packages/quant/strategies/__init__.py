from packages.quant.strategies.base import (
    AnalysisResult,
    Direction,
    MarketContext,
    Strategy,
    StrategyBase,
    StrategySignal,
)
from packages.quant.strategies.breakout import BreakoutStrategy
from packages.quant.strategies.mean_reversion import MeanReversionStrategy
from packages.quant.strategies.momentum import MomentumStrategy
from packages.quant.strategies.trend_following import TrendFollowingStrategy

# The Phase 2 strategy universe (docs/blueprint/12-roadmap.md). Adding a new
# strategy is: implement StrategyBase, register it here — nothing else in
# the pipeline (worker, scoring, API) needs to change.
ALL_STRATEGIES: list[Strategy] = [
    TrendFollowingStrategy(),
    MomentumStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
]

__all__ = [
    "AnalysisResult",
    "Direction",
    "MarketContext",
    "Strategy",
    "StrategyBase",
    "StrategySignal",
    "ALL_STRATEGIES",
    "TrendFollowingStrategy",
    "MomentumStrategy",
    "BreakoutStrategy",
    "MeanReversionStrategy",
]
