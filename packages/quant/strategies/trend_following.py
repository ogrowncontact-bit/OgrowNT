"""Trend Following — docs/blueprint/12-roadmap.md Fase 2, Strategy 01.

Enters in the direction of an established trend (EMA fast/slow spread,
normalized by ATR — see packages/quant/indicators/core.py:trend_strength).
Stop is placed beyond the recent swing low/high, target at a fixed R multiple.
"""
from __future__ import annotations

from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategyBase, StrategySignal

ENTRY_THRESHOLD = 0.5  # trend_strength magnitude (ATR units) required to act
RISK_REWARD = 2.0
ATR_STOP_BUFFER = 0.5  # extra ATR beyond the swing low/high, for noise


class TrendFollowingStrategy(StrategyBase):
    """Numeric constants are constructor parameters (defaulting to the
    module-level constants above) so packages/backtest/stability.py can
    perturb them and check the backtest verdict doesn't flip sign — the
    "parameter stability" anti-overfitting check in
    docs/blueprint/10-backtesting-paper-trading.md. Live code
    (packages/quant/strategies/__init__.py) always instantiates with
    defaults, so this is a no-op for everything before Phase 6.
    """

    code = "trend_following_v1"
    name = "Trend Following"
    version = "1.0"
    family = "trend"
    best_regimes = frozenset({"trending_bull", "trending_bear"})
    worst_regimes = frozenset({"ranging"})

    def __init__(
        self, entry_threshold: float = ENTRY_THRESHOLD, risk_reward: float = RISK_REWARD, atr_stop_buffer: float = ATR_STOP_BUFFER
    ) -> None:
        self.entry_threshold = entry_threshold
        self.risk_reward = risk_reward
        self.atr_stop_buffer = atr_stop_buffer

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        ts = ctx.indicators.trend_strength
        if ts is None:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "no_trend_strength"})

        direction = "long" if ts > 0 else "short"
        strength = min(1.0, abs(ts) / (self.entry_threshold * 4))
        return AnalysisResult(
            direction=direction,
            strength=strength,
            rationale={"trend_strength": ts, "threshold": self.entry_threshold},
        )

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        analysis = self.analyze(ctx)
        ts = ctx.indicators.trend_strength
        atr_v = ctx.indicators.atr_14
        if analysis.direction is None or ts is None or atr_v is None or atr_v <= 0:
            return None
        if abs(ts) < self.entry_threshold:
            return None

        entry = ctx.indicators.close
        if analysis.direction == "long":
            swing = ctx.indicators.recent_low_20 or (entry - 2 * atr_v)
            stop = min(swing, entry) - self.atr_stop_buffer * atr_v
            risk = entry - stop
            target = entry + self.risk_reward * risk
        else:
            swing = ctx.indicators.recent_high_20 or (entry + 2 * atr_v)
            stop = max(swing, entry) + self.atr_stop_buffer * atr_v
            risk = stop - entry
            target = entry - self.risk_reward * risk

        if risk <= 0:
            return None

        return StrategySignal(
            direction=analysis.direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strength=analysis.strength,
            rationale={
                **analysis.rationale,
                "regime": ctx.regime.regime,
                "atr": atr_v,
            },
        )

