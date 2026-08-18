"""Pattern Engine — docs/blueprint/04-agents-architecture.md#agent-05.

Classifies what's currently happening for one asset, independent of any
specific strategy's opinion on what to do about it — a different question
than the Strategy Engine asks, even though both read the same indicators.
Detections feed the Opportunity Scoring Engine's `pattern` component
(packages/quant/scoring) and get their own win-rate tracking
(pattern_performance, updated by apps/worker/trade_monitor.py).

`strength` and `confidence` answer different questions and are never
conflated: strength is how far past its threshold the pattern's own
magnitude sits (a bigger trend, a wider breakout); confidence is how much
the candles behind the reading can be trusted
(packages/quant/indicators/core.py's `data_quality_confidence`), regardless
of how strong the resulting number looks. A pattern computed from degraded
data can still show high strength -- it just shouldn't be trusted as much.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import IndicatorSet, avg_volume, data_quality_confidence, recent_high, recent_low

PATTERN_TREND = "trend"
PATTERN_BREAKOUT = "breakout"
PATTERN_REVERSAL = "reversal"
PATTERN_MOMENTUM = "momentum"
PATTERN_MEAN_REVERSION = "mean_reversion"
PATTERN_VOLATILITY = "volatility"
PATTERN_ANOMALY = "anomaly"
PATTERN_CROSS_ASSET = "cross_asset"

CLASS_TECHNICAL = "technical"
CLASS_STATISTICAL = "statistical"
CLASS_CROSS_MARKET = "cross_market"

TREND_STRENGTH_THRESHOLD = 0.5
BREAKOUT_LOOKBACK = 20
BREAKOUT_VOLUME_MULT = 1.2
REVERSAL_LOOKBACK = 10
MOMENTUM_ROC_THRESHOLD = 0.01
MEAN_REVERSION_MIN_DEVIATION = 0.005
VOLATILITY_HIGH = 0.015
VOLATILITY_LOW = 0.004
ANOMALY_Z_THRESHOLD = 2.5
CROSS_ASSET_MIN_DIVERGENCE = 0.01


BREAKOUT_STATE_CONFIRMED = "confirmed"
BREAKOUT_STATE_POSSIBLE = "possible"
# A possible (unconfirmed) breakout is real but weaker evidence than a
# volume-confirmed one, so it's capped well below what a confirmed
# breakout of the same price size would score.
BREAKOUT_POSSIBLE_STRENGTH_CAP = 0.5


@dataclass(frozen=True)
class PatternDetection:
    pattern_type: str
    pattern_class: str
    direction: str  # bullish | bearish | neutral
    strength: float  # 0.0 - 1.0 -- how strong the pattern itself is
    confidence: float  # 0.0 - 1.0 -- how trustworthy the inputs behind it are
    metadata: dict = field(default_factory=dict)


def detect_trend(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    ts = indicators.trend_strength
    if ts is None or abs(ts) < TREND_STRENGTH_THRESHOLD:
        return None
    direction = "bullish" if ts > 0 else "bearish"
    strength = min(1.0, abs(ts) / (TREND_STRENGTH_THRESHOLD * 4))
    return PatternDetection(
        PATTERN_TREND, CLASS_TECHNICAL, direction, strength, data_quality_confidence(candles), {"trend_strength": ts}
    )


def detect_breakout(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    """Differentiates CONFIRMED_BREAKOUT (price broke the level with
    above-average volume) from POSSIBLE_BREAKOUT (price broke the level but
    volume didn't confirm it yet) -- a failed breakout that reverses back
    inside the range is detect_reversal's job, a different pattern entirely."""
    if len(candles) < BREAKOUT_LOOKBACK + 1:
        return None
    prior = candles[-(BREAKOUT_LOOKBACK + 1) : -1]
    current = candles[-1]
    prior_high, prior_low = recent_high(prior, BREAKOUT_LOOKBACK), recent_low(prior, BREAKOUT_LOOKBACK)
    avg_vol = avg_volume(prior, BREAKOUT_LOOKBACK)
    if prior_high is None or prior_low is None or not avg_vol:
        return None
    confirmed = current.volume >= BREAKOUT_VOLUME_MULT * avg_vol
    state = BREAKOUT_STATE_CONFIRMED if confirmed else BREAKOUT_STATE_POSSIBLE
    confidence = data_quality_confidence(candles)

    if current.close > prior_high:
        size = (current.close - prior_high) / prior_high
        strength = min(1.0, size / 0.01)
        if not confirmed:
            strength = min(strength, BREAKOUT_POSSIBLE_STRENGTH_CAP)
        return PatternDetection(
            PATTERN_BREAKOUT, CLASS_TECHNICAL, "bullish", strength, confidence,
            {"level": prior_high, "breakout_state": state, "volume_confirmed": confirmed},
        )
    if current.close < prior_low:
        size = (prior_low - current.close) / prior_low
        strength = min(1.0, size / 0.01)
        if not confirmed:
            strength = min(strength, BREAKOUT_POSSIBLE_STRENGTH_CAP)
        return PatternDetection(
            PATTERN_BREAKOUT, CLASS_TECHNICAL, "bearish", strength, confidence,
            {"level": prior_low, "breakout_state": state, "volume_confirmed": confirmed},
        )
    return None


def detect_reversal(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    """A failed breakout: price pierced a recent extreme intrabar but closed
    back inside the prior range -- a classic rejection signature."""
    if len(candles) < REVERSAL_LOOKBACK + 1:
        return None
    prior = candles[-(REVERSAL_LOOKBACK + 1) : -1]
    current = candles[-1]
    prior_high, prior_low = recent_high(prior, REVERSAL_LOOKBACK), recent_low(prior, REVERSAL_LOOKBACK)
    if prior_high is None or prior_low is None:
        return None
    confidence = data_quality_confidence(candles)

    if current.high > prior_high and current.close < prior_high:
        rejection = (current.high - current.close) / current.high
        return PatternDetection(
            PATTERN_REVERSAL, CLASS_TECHNICAL, "bearish", min(1.0, rejection / 0.01), confidence,
            {"level": prior_high, "breakout_state": "failed"},
        )
    if current.low < prior_low and current.close > prior_low:
        rejection = (current.close - current.low) / current.low
        return PatternDetection(
            PATTERN_REVERSAL, CLASS_TECHNICAL, "bullish", min(1.0, rejection / 0.01), confidence,
            {"level": prior_low, "breakout_state": "failed"},
        )
    return None


def detect_momentum(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    roc, rsi = indicators.roc_10, indicators.rsi_14
    if roc is None or rsi is None:
        return None
    confidence = data_quality_confidence(candles)
    if roc >= MOMENTUM_ROC_THRESHOLD and rsi >= 55:
        return PatternDetection(
            PATTERN_MOMENTUM, CLASS_TECHNICAL, "bullish", min(1.0, abs(roc) / (MOMENTUM_ROC_THRESHOLD * 4)), confidence,
            {"roc": roc, "rsi": rsi},
        )
    if roc <= -MOMENTUM_ROC_THRESHOLD and rsi <= 45:
        return PatternDetection(
            PATTERN_MOMENTUM, CLASS_TECHNICAL, "bearish", min(1.0, abs(roc) / (MOMENTUM_ROC_THRESHOLD * 4)), confidence,
            {"roc": roc, "rsi": rsi},
        )
    return None


def detect_mean_reversion(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    rsi, sma_slow, close = indicators.rsi_14, indicators.sma_slow, indicators.close
    if rsi is None or not sma_slow:
        return None
    deviation = (close - sma_slow) / sma_slow
    confidence = data_quality_confidence(candles)
    if rsi <= 30 and deviation <= -MEAN_REVERSION_MIN_DEVIATION:
        return PatternDetection(
            PATTERN_MEAN_REVERSION, CLASS_TECHNICAL, "bullish", min(1.0, (30 - rsi) / 15), confidence,
            {"rsi": rsi, "deviation": deviation},
        )
    if rsi >= 70 and deviation >= MEAN_REVERSION_MIN_DEVIATION:
        return PatternDetection(
            PATTERN_MEAN_REVERSION, CLASS_TECHNICAL, "bearish", min(1.0, (rsi - 70) / 15), confidence,
            {"rsi": rsi, "deviation": deviation},
        )
    return None


def detect_volatility(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    vol = indicators.realized_vol_20
    if vol is None:
        return None
    confidence = data_quality_confidence(candles)
    if vol >= VOLATILITY_HIGH:
        return PatternDetection(
            PATTERN_VOLATILITY, CLASS_STATISTICAL, "neutral", min(1.0, vol / (VOLATILITY_HIGH * 3)), confidence,
            {"realized_vol_20": vol, "state": "expansion"},
        )
    if vol <= VOLATILITY_LOW:
        strength = min(1.0, (VOLATILITY_LOW - vol) / VOLATILITY_LOW + 0.3)
        return PatternDetection(
            PATTERN_VOLATILITY, CLASS_STATISTICAL, "neutral", strength, confidence,
            {"realized_vol_20": vol, "state": "compression"},
        )
    return None


def detect_anomaly(candles: list[Candle], indicators: IndicatorSet) -> PatternDetection | None:
    """A single-bar return well outside the recent return distribution —
    z-score outlier detection. Statistical, not directional conviction."""
    if len(candles) < 21:
        return None
    closes = [c.close for c in candles[-21:]]
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    if len(returns) < 20:
        return None
    latest_return, history = returns[-1], returns[:-1]
    mean = sum(history) / len(history)
    variance = sum((r - mean) ** 2 for r in history) / len(history)
    std = variance**0.5
    if std == 0:
        return None
    z_score = (latest_return - mean) / std
    if abs(z_score) < ANOMALY_Z_THRESHOLD:
        return None
    direction = "bullish" if z_score > 0 else "bearish"
    strength = min(1.0, (abs(z_score) - ANOMALY_Z_THRESHOLD) / ANOMALY_Z_THRESHOLD + 0.5)
    return PatternDetection(
        PATTERN_ANOMALY, CLASS_STATISTICAL, direction, strength, data_quality_confidence(candles[-21:]), {"z_score": z_score}
    )


def detect_cross_asset(own_return: float | None, peer_return: float | None, peer_symbol: str) -> PatternDetection | None:
    """Divergence from a highly-correlated peer's latest move. Needs the
    peer's return supplied by the caller (packages/risk/correlation_guard
    already computes the correlation matrix; this detector has no DB access
    of its own, matching every other detector's pure-function shape). No
    candle window of its own to derive confidence from -- both returns are
    already-validated numbers from the correlation guard, so confidence is
    fixed at 1.0 rather than guessed."""
    if own_return is None or peer_return is None:
        return None
    divergence = own_return - peer_return
    if abs(divergence) < CROSS_ASSET_MIN_DIVERGENCE:
        return None
    direction = "bullish" if divergence > 0 else "bearish"
    strength = min(1.0, abs(divergence) / (CROSS_ASSET_MIN_DIVERGENCE * 3))
    return PatternDetection(
        PATTERN_CROSS_ASSET, CLASS_CROSS_MARKET, direction, strength, 1.0,
        {"divergence": divergence, "peer_symbol": peer_symbol},
    )


# Detectors sharing the (candles, indicators) signature — detect_cross_asset
# needs extra context (a correlated peer's return) and is called separately.
STANDARD_DETECTORS = [
    detect_trend, detect_breakout, detect_reversal, detect_momentum,
    detect_mean_reversion, detect_volatility, detect_anomaly,
]


def detect_all(candles: list[Candle], indicators: IndicatorSet) -> list[PatternDetection]:
    return [d for detector in STANDARD_DETECTORS if (d := detector(candles, indicators)) is not None]
