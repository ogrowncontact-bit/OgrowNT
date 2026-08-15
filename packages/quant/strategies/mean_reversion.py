"""Mean Reversion — docs/blueprint/12-roadmap.md Fase 2, Strategy 04.

Counter-trend: enters when RSI is at an extreme AND price has deviated
meaningfully from its slow SMA, expecting reversion toward the mean. Best
suited to ranging/low-volatility regimes — trending markets can stay
"overbought"/"oversold" for a long time, which is exactly why this strategy
is marked worst-fit for trending/high-vol regimes.
"""
from __future__ import annotations

from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategyBase, StrategySignal

RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
MIN_DEVIATION = 0.005  # price must be at least 0.5% away from SMA(30)
RISK_REWARD = 1.5
ATR_STOP_MULT = 1.2


class MeanReversionStrategy(StrategyBase):
    code = "mean_reversion_v1"
    name = "Mean Reversion"
    version = "1.0"
    family = "mean_reversion"
    best_regimes = frozenset({"ranging", "low_volatility"})
    worst_regimes = frozenset({"trending_bull", "trending_bear", "high_volatility"})

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        rsi, sma_slow, close = ctx.indicators.rsi_14, ctx.indicators.sma_slow, ctx.indicators.close
        if rsi is None or sma_slow is None or sma_slow == 0:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "insufficient_data"})

        deviation = (close - sma_slow) / sma_slow
        oversold = rsi <= RSI_OVERSOLD and deviation <= -MIN_DEVIATION
        overbought = rsi >= RSI_OVERBOUGHT and deviation >= MIN_DEVIATION
        if not oversold and not overbought:
            return AnalysisResult(direction=None, strength=0.0, rationale={"rsi": rsi, "deviation": deviation})

        direction = "long" if oversold else "short"
        rsi_extremity = (RSI_OVERSOLD - rsi) if oversold else (rsi - RSI_OVERBOUGHT)
        strength = min(1.0, max(0.0, rsi_extremity) / 15.0)
        return AnalysisResult(direction=direction, strength=strength, rationale={"rsi": rsi, "deviation": deviation})

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        analysis = self.analyze(ctx)
        atr_v, sma_slow = ctx.indicators.atr_14, ctx.indicators.sma_slow
        if analysis.direction is None or atr_v is None or atr_v <= 0 or sma_slow is None:
            return None

        entry = ctx.indicators.close
        risk = ATR_STOP_MULT * atr_v
        if analysis.direction == "long":
            stop = entry - risk
            target = min(sma_slow, entry + RISK_REWARD * risk)  # revert toward the mean, capped by R multiple
        else:
            stop = entry + risk
            target = max(sma_slow, entry - RISK_REWARD * risk)

        return StrategySignal(
            direction=analysis.direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strength=analysis.strength,
            rationale={**analysis.rationale, "regime": ctx.regime.regime, "sma_slow": sma_slow, "atr": atr_v},
        )
