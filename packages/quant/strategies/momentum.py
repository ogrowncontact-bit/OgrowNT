"""Momentum — docs/blueprint/12-roadmap.md Fase 2, Strategy 02.

Independent of trend_following's EMA/ATR read: uses rate-of-change (ROC) plus
RSI level to catch short-horizon momentum bursts, confirmed by regime.
"""
from __future__ import annotations

from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategyBase, StrategySignal

ROC_THRESHOLD = 0.01  # +/-1% over the ROC lookback window to call it momentum
RSI_BULL = 55.0
RSI_BEAR = 45.0
RISK_REWARD = 1.8
ATR_STOP_MULT = 1.5


class MomentumStrategy(StrategyBase):
    code = "momentum_v1"
    name = "Momentum"
    version = "1.0"
    family = "momentum"
    best_regimes = frozenset({"trending_bull", "trending_bear"})
    worst_regimes = frozenset({"ranging", "low_volatility"})

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        roc, rsi = ctx.indicators.roc_10, ctx.indicators.rsi_14
        if roc is None or rsi is None:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "insufficient_data"})

        bullish = roc >= ROC_THRESHOLD and rsi >= RSI_BULL
        bearish = roc <= -ROC_THRESHOLD and rsi <= RSI_BEAR
        if not bullish and not bearish:
            return AnalysisResult(direction=None, strength=0.0, rationale={"roc": roc, "rsi": rsi})

        direction = "long" if bullish else "short"
        strength = min(1.0, abs(roc) / (ROC_THRESHOLD * 4))
        return AnalysisResult(direction=direction, strength=strength, rationale={"roc": roc, "rsi": rsi})

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        analysis = self.analyze(ctx)
        atr_v = ctx.indicators.atr_14
        if analysis.direction is None or atr_v is None or atr_v <= 0:
            return None

        entry = ctx.indicators.close
        risk = ATR_STOP_MULT * atr_v
        if analysis.direction == "long":
            stop, target = entry - risk, entry + RISK_REWARD * risk
        else:
            stop, target = entry + risk, entry - RISK_REWARD * risk

        return StrategySignal(
            direction=analysis.direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strength=analysis.strength,
            rationale={**analysis.rationale, "regime": ctx.regime.regime, "atr": atr_v},
        )
