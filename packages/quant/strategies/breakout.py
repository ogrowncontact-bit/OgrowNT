"""Breakout — docs/blueprint/12-roadmap.md Fase 2, Strategy 03.

Enters when the current close breaks the prior N-bar high/low with
above-average volume. Stop sits back inside the broken range.
"""
from __future__ import annotations

from packages.quant.indicators.core import avg_volume, recent_high, recent_low
from packages.quant.strategies.base import AnalysisResult, Direction, MarketContext, StrategyBase, StrategySignal

LOOKBACK = 20
VOLUME_CONFIRMATION_MULT = 1.2  # current volume must exceed this * average
RISK_REWARD = 2.2
ATR_STOP_BUFFER = 0.3


class BreakoutStrategy(StrategyBase):
    """Numeric constants are constructor parameters (see
    packages/quant/strategies/trend_following.py's docstring for why)."""

    code = "breakout_v1"
    name = "Breakout"
    version = "1.0"
    family = "breakout"
    best_regimes = frozenset({"trending_bull", "trending_bear", "low_volatility"})
    worst_regimes = frozenset({"ranging", "high_volatility"})

    def __init__(
        self, lookback: int = LOOKBACK, volume_confirmation_mult: float = VOLUME_CONFIRMATION_MULT,
        risk_reward: float = RISK_REWARD, atr_stop_buffer: float = ATR_STOP_BUFFER,
    ) -> None:
        self.lookback = lookback
        self.volume_confirmation_mult = volume_confirmation_mult
        self.risk_reward = risk_reward
        self.atr_stop_buffer = atr_stop_buffer

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        candles = ctx.candles
        if len(candles) < self.lookback + 1:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "insufficient_data"})

        prior = candles[-(self.lookback + 1) : -1]  # excludes the current bar
        prior_high, prior_low = recent_high(prior, self.lookback), recent_low(prior, self.lookback)
        current = candles[-1]
        avg_vol = avg_volume(prior, self.lookback)
        if prior_high is None or prior_low is None or avg_vol is None or avg_vol == 0:
            return AnalysisResult(direction=None, strength=0.0, rationale={"reason": "insufficient_data"})

        volume_confirmed = current.volume >= self.volume_confirmation_mult * avg_vol
        breaks_up = current.close > prior_high
        breaks_down = current.close < prior_low

        if not volume_confirmed or (not breaks_up and not breaks_down):
            return AnalysisResult(
                direction=None,
                strength=0.0,
                rationale={"prior_high": prior_high, "prior_low": prior_low, "volume_confirmed": volume_confirmed},
            )

        direction: Direction = "long" if breaks_up else "short"
        breakout_size = (current.close - prior_high) / prior_high if breaks_up else (prior_low - current.close) / prior_low
        strength = min(1.0, max(0.0, breakout_size) / 0.01)
        return AnalysisResult(
            direction=direction,
            strength=strength,
            rationale={"prior_high": prior_high, "prior_low": prior_low, "volume_confirmed": True},
        )

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        analysis = self.analyze(ctx)
        atr_v = ctx.indicators.atr_14
        if analysis.direction is None or atr_v is None or atr_v <= 0:
            return None

        entry = ctx.indicators.close
        prior_high = analysis.rationale["prior_high"]
        prior_low = analysis.rationale["prior_low"]
        if analysis.direction == "long":
            stop = prior_high - self.atr_stop_buffer * atr_v
            risk = entry - stop
            target = entry + self.risk_reward * risk
        else:
            stop = prior_low + self.atr_stop_buffer * atr_v
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
            rationale={**analysis.rationale, "regime": ctx.regime.regime, "atr": atr_v},
        )
