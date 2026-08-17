"""Momentum — docs/blueprint/12-roadmap.md Fase 2, Strategy 02.

Independent of trend_following's EMA/ATR read: uses rate-of-change (ROC) plus
RSI level to catch short-horizon momentum bursts, confirmed by regime.
"""
from __future__ import annotations

from packages.quant.strategies.base import AnalysisResult, Direction, MarketContext, StrategyBase, StrategySignal

ROC_THRESHOLD = 0.01  # +/-1% over the ROC lookback window to call it momentum
RSI_BULL = 55.0
RSI_BEAR = 45.0
RISK_REWARD = 1.8
ATR_STOP_MULT = 1.5


class MomentumStrategy(StrategyBase):
    """Numeric constants are constructor parameters (see
    packages/quant/strategies/trend_following.py's docstring for why)."""

    code = "momentum_v1"
    name = "Momentum"
    version = "1.0"
    family = "momentum"
    best_regimes = frozenset({"trending_bull", "trending_bear"})
    worst_regimes = frozenset({"ranging", "low_volatility"})

    def __init__(
        self, roc_threshold: float = ROC_THRESHOLD, rsi_bull: float = RSI_BULL, rsi_bear: float = RSI_BEAR,
        risk_reward: float = RISK_REWARD, atr_stop_mult: float = ATR_STOP_MULT,
    ) -> None:
        self.roc_threshold = roc_threshold
        self.rsi_bull = rsi_bull
        self.rsi_bear = rsi_bear
        self.risk_reward = risk_reward
        self.atr_stop_mult = atr_stop_mult

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        roc, rsi = ctx.indicators.roc_10, ctx.indicators.rsi_14
        if roc is None or rsi is None:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "insufficient_data"})

        bullish = roc >= self.roc_threshold and rsi >= self.rsi_bull
        bearish = roc <= -self.roc_threshold and rsi <= self.rsi_bear
        if not bullish and not bearish:
            return AnalysisResult(direction=None, strength=0.0, rationale={"roc": roc, "rsi": rsi})

        direction: Direction = "long" if bullish else "short"
        strength = min(1.0, abs(roc) / (self.roc_threshold * 4))
        return AnalysisResult(direction=direction, strength=strength, rationale={"roc": roc, "rsi": rsi})

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        analysis = self.analyze(ctx)
        atr_v = ctx.indicators.atr_14
        if analysis.direction is None or atr_v is None or atr_v <= 0:
            return None

        entry = ctx.indicators.close
        risk = self.atr_stop_mult * atr_v
        if analysis.direction == "long":
            stop, target = entry - risk, entry + self.risk_reward * risk
        else:
            stop, target = entry + risk, entry - self.risk_reward * risk

        return StrategySignal(
            direction=analysis.direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strength=analysis.strength,
            rationale={**analysis.rationale, "regime": ctx.regime.regime, "atr": atr_v},
        )
