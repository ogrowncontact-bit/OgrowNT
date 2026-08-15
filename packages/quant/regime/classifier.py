"""Market Regime Engine — docs/blueprint/04-agents-architecture.md#agent-06.

Phase 2 implements a rule-based classifier over five of the nine regimes in
the full taxonomy (docs/blueprint/02-database-schema.md#market_regimes):
`trending_bull`, `trending_bear`, `ranging`, `high_volatility`,
`low_volatility`. `panic`, `euphoria` and `transition` require the News
Intelligence Agent (Phase 4) to distinguish a volatility spike driven by a
real shock from ordinary high volatility — until then those three states are
never emitted. `unknown` is returned when there isn't enough history yet.
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
