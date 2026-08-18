"""Technical indicators — docs/blueprint/04-agents-architecture.md#agent-04.

Pure functions over price series so they are trivial to unit test and to
extend later (new indicators are just new functions / a new field on
IndicatorSet — no framework required, per docs/blueprint/01-repo-structure.md).
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.data.connectors.market.base import Candle


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return _ema_series(values, period)[-1]


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    true_ranges = []
    for i in range(-period, 0):
        candle = candles[i]
        prev_close = candles[i - 1].close
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )
    return sum(true_ranges) / period


def realized_volatility(closes: list[float], period: int = 20) -> float | None:
    if len(closes) < period + 1:
        return None
    window = closes[-(period + 1) :]
    returns = [(window[i] - window[i - 1]) / window[i - 1] for i in range(1, len(window))]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return variance**0.5


def trend_strength(closes: list[float], atr_value: float | None, fast: int = 12, slow: int = 26) -> float | None:
    """(EMA fast - EMA slow) normalized by ATR — an ADX-like directional proxy.

    Positive = uptrend, negative = downtrend, magnitude = strength. Not a
    substitute for a proper ADX, but cheap, explainable, and good enough to
    drive regime classification and strategy signals in Phase 2.
    """
    if not atr_value:
        return None
    ema_fast, ema_slow = ema(closes, fast), ema(closes, slow)
    if ema_fast is None or ema_slow is None:
        return None
    return (ema_fast - ema_slow) / atr_value


def roc(closes: list[float], period: int = 10) -> float | None:
    """Rate of change over `period` bars, as a fraction (0.02 = +2%)."""
    if len(closes) < period + 1:
        return None
    base = closes[-1 - period]
    if base == 0:
        return None
    return (closes[-1] - base) / base


def avg_volume(candles: list[Candle], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    return sum(c.volume for c in candles[-period:]) / period


def recent_high(candles: list[Candle], lookback: int = 20) -> float | None:
    if len(candles) < lookback:
        return None
    return max(c.high for c in candles[-lookback:])


def recent_low(candles: list[Candle], lookback: int = 20) -> float | None:
    if len(candles) < lookback:
        return None
    return min(c.low for c in candles[-lookback:])


_DATA_QUALITY_WEIGHT = {"high": 1.0, "degraded": 0.5, "unavailable": 0.0}


def data_quality_confidence(candles: list[Candle]) -> float:
    """0.0-1.0: how much the candles behind a reading can be trusted, as
    opposed to how strong the reading itself is (packages/quant/patterns's
    strength vs confidence distinction, docs/blueprint's "no hallucinated
    data" rule applied to detector inputs rather than storage). Reused by
    the Pattern Engine and the Opportunity Scoring Engine's confidence
    component so both agree on what "trustworthy inputs" means."""
    if not candles:
        return 0.0
    return sum(_DATA_QUALITY_WEIGHT.get(c.data_quality, 0.0) for c in candles) / len(candles)


@dataclass(frozen=True)
class IndicatorSet:
    close: float
    sma_fast: float | None
    sma_slow: float | None
    ema_fast: float | None
    ema_slow: float | None
    rsi_14: float | None
    atr_14: float | None
    realized_vol_20: float | None
    trend_strength: float | None
    roc_10: float | None
    avg_volume_20: float | None
    recent_high_20: float | None
    recent_low_20: float | None


# Minimum candles needed for every field above to resolve (slowest is SMA(30)).
MIN_CANDLES_REQUIRED = 30


def compute_indicators(candles: list[Candle]) -> IndicatorSet:
    """candles must be chronological ascending (oldest first, latest last)."""
    closes = [c.close for c in candles]
    atr_value = atr(candles, 14)
    return IndicatorSet(
        close=closes[-1],
        sma_fast=sma(closes, 10),
        sma_slow=sma(closes, 30),
        ema_fast=ema(closes, 12),
        ema_slow=ema(closes, 26),
        rsi_14=rsi(closes, 14),
        atr_14=atr_value,
        realized_vol_20=realized_volatility(closes, 20),
        trend_strength=trend_strength(closes, atr_value),
        roc_10=roc(closes, 10),
        avg_volume_20=avg_volume(candles, 20),
        recent_high_20=recent_high(candles, 20),
        recent_low_20=recent_low(candles, 20),
    )
