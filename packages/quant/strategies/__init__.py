from packages.quant.strategies.base import (
    AnalysisResult,
    Direction,
    MarketContext,
    RiskProfile,
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

# code -> class, for packages/backtest (rebuilding a strategy instance with
# perturbed params for parameter-stability testing) and any other caller
# that needs a fresh instance rather than the shared ALL_STRATEGIES singletons.
STRATEGY_CLASSES: dict[str, type] = {
    TrendFollowingStrategy.code: TrendFollowingStrategy,
    MomentumStrategy.code: MomentumStrategy,
    BreakoutStrategy.code: BreakoutStrategy,
    MeanReversionStrategy.code: MeanReversionStrategy,
}

__all__ = [
    "AnalysisResult",
    "Direction",
    "MarketContext",
    "RiskProfile",
    "Strategy",
    "StrategyBase",
    "StrategySignal",
    "ALL_STRATEGIES",
    "STRATEGY_CLASSES",
    "TrendFollowingStrategy",
    "MomentumStrategy",
    "BreakoutStrategy",
    "MeanReversionStrategy",
]
