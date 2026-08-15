"""Market Regime Engine — docs/blueprint/04-agents-architecture.md#agent-06.

`classify_regime()` is a rule-based classifier over five of the nine regimes
in the full taxonomy (docs/blueprint/02-database-schema.md#market_regimes):
`trending_bull`, `trending_bear`, `ranging`, `high_volatility`,
`low_volatility`, plus `unknown` when there isn't enough history yet.

`panic`, `euphoria` and `transition` need the News Intelligence Agent
(packages/llm/news_intelligence.py) to tell a volatility spike driven by a
real, identifiable shock apart from ordinary high volatility —
`classify_regime_with_news()` layers that on top of the base classification
and is what the worker actually calls once news_impact data exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import MIN_CANDLES_REQUIRED, compute_indicators

REGIME_UNKNOWN = "unknown"
REGIME_TRENDING_BULL = "trending_bull"
REGIME_TRENDING_BEAR = "trending_bear"
REGIME_RANGING = "ranging"
REGIME_HIGH_VOLATILITY = "high_volatility"
REGIME_LOW_VOLATILITY = "low_volatility"
REGIME_PANIC = "panic"
REGIME_EUPHORIA = "euphoria"
REGIME_TRANSITION = "transition"

# Thresholds — configuration, not physics. Revisit once Phase 5 (Learning
# Engine) can measure whether these boundaries actually separate strategy
# performance the way they're meant to.
TREND_STRENGTH_THRESHOLD = 0.5  # |EMA fast - EMA slow| in ATR units
HIGH_VOL_THRESHOLD = 0.015  # realized volatility (stdev of returns) per bar
LOW_VOL_THRESHOLD = 0.004


@dataclass(frozen=True)
class RegimeResult:
    regime: str
    confidence: float
    features: dict = field(default_factory=dict)


def classify_regime(candles: list[Candle]) -> RegimeResult:
    if len(candles) < MIN_CANDLES_REQUIRED:
        return RegimeResult(
            regime=REGIME_UNKNOWN,
            confidence=0.0,
            features={"reason": "insufficient_history", "candles": len(candles)},
        )

    ind = compute_indicators(candles)
    features = {
        "trend_strength": ind.trend_strength,
        "realized_vol_20": ind.realized_vol_20,
    }

    if ind.trend_strength is not None and abs(ind.trend_strength) >= TREND_STRENGTH_THRESHOLD:
        regime = REGIME_TRENDING_BULL if ind.trend_strength > 0 else REGIME_TRENDING_BEAR
        confidence = min(1.0, abs(ind.trend_strength) / (TREND_STRENGTH_THRESHOLD * 3))
        return RegimeResult(regime=regime, confidence=round(confidence, 3), features=features)

    if ind.realized_vol_20 is not None and ind.realized_vol_20 >= HIGH_VOL_THRESHOLD:
        confidence = min(1.0, ind.realized_vol_20 / (HIGH_VOL_THRESHOLD * 3))
        return RegimeResult(regime=REGIME_HIGH_VOLATILITY, confidence=round(confidence, 3), features=features)

    if ind.realized_vol_20 is not None and ind.realized_vol_20 <= LOW_VOL_THRESHOLD:
        confidence = min(1.0, (LOW_VOL_THRESHOLD - ind.realized_vol_20) / LOW_VOL_THRESHOLD + 0.5)
        return RegimeResult(regime=REGIME_LOW_VOLATILITY, confidence=round(confidence, 3), features=features)

    return RegimeResult(regime=REGIME_RANGING, confidence=0.5, features=features)


@dataclass(frozen=True)
class NewsSignal:
    """The minimal slice of a news_impact row the regime classifier needs —
    callers filter to whatever's recent/relevant for the asset in question
    (e.g. within its horizon_hours window) before passing these in."""

    direction: str  # bullish | bearish | neutral
    impact: str  # low | medium | high
    confidence: float


# A volatility spike only earns panic/euphoria (vs. staying ordinary
# high_volatility) when news explains it with real conviction — otherwise
# it's unexplained noise, not a documented shock.
NEWS_REGIME_MIN_CONFIDENCE = 0.65


def classify_regime_with_news(candles: list[Candle], recent_news: list[NewsSignal]) -> RegimeResult:
    """Base price-action regime, reclassified into panic/euphoria/transition
    when high_volatility coincides with real, recent news:
      - one-directional high-impact, high-confidence bearish news -> panic
      - one-directional high-impact, high-confidence bullish news -> euphoria
      - news exists but is mixed or not confidently one-directional -> transition
        (the volatility has an identifiable cause, but the market hasn't
        resolved which way it's going)
      - no news at all -> stays ordinary high_volatility, unexplained
    """
    base = classify_regime(candles)
    if base.regime != REGIME_HIGH_VOLATILITY or not recent_news:
        return base

    strong = [n for n in recent_news if n.impact == "high" and n.confidence >= NEWS_REGIME_MIN_CONFIDENCE]
    bearish = [n for n in strong if n.direction == "bearish"]
    bullish = [n for n in strong if n.direction == "bullish"]

    features = {**base.features, "news_count": len(recent_news), "strong_news_count": len(strong)}

    if bearish and not bullish:
        confidence = max(base.confidence, max(n.confidence for n in bearish))
        return RegimeResult(regime=REGIME_PANIC, confidence=round(confidence, 3), features=features)
    if bullish and not bearish:
        confidence = max(base.confidence, max(n.confidence for n in bullish))
        return RegimeResult(regime=REGIME_EUPHORIA, confidence=round(confidence, 3), features=features)

    # News exists (someone published something relevant) but doesn't give a
    # clean, high-confidence, one-directional read -> the market's reaction
    # to it is still unresolved.
    return RegimeResult(regime=REGIME_TRANSITION, confidence=round(base.confidence * 0.8, 3), features=features)
