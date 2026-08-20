"""Volatility Engine -- "PROMPT 11" §54-57 (realized/ATR/percentile/regime/
acceleration, detecting compression/expansion/spike/collapse transitions).

Reuses packages/quant/indicators/core.py::realized_volatility/atr for the
underlying measurement and packages/market/liquidity.py::percentile_rank
for the ranking (the same generic "value vs population" function, just
applied to a per-asset historical volatility series here instead of a
cross-asset volume series there). Only the percentile-ranking/regime-
labeling/transition-detection layer below is genuinely new.

"Implied volatility when available" from the prompt's component list is
not implemented: no provider anywhere in this codebase serves an options
market or an IV surface, so there is nothing honest to read -- an
unconditionally-None field would just be a stub, not a feature (see
docs/blueprint's "no hallucinated data" / "no half-finished
implementations" conventions). Realized volatility (from real OHLCV) is
the whole signal here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.market.liquidity import percentile_rank
from packages.quant.indicators.core import realized_volatility
from packages.shared.market_data import get_recent_candles
from packages.shared.models import VolatilityEvent

logger = logging.getLogger("market.volatility")

TIMEFRAME = "1m"
_VOL_PERIOD = 20
# Enough candles for one realized_volatility reading (_VOL_PERIOD + 1) plus
# a real population of at least 10 prior readings to percentile-rank against.
_MIN_CANDLES = _VOL_PERIOD + 11
_LOOKBACK_CANDLES = 200

# -- closed vocabulary -- matches ck_volatility_events_* CHECK constraints --
REGIME_LOW = "low"
REGIME_NORMAL = "normal"
REGIME_HIGH = "high"
REGIME_EXTREME = "extreme"
_REGIME_ORDER = (REGIME_LOW, REGIME_NORMAL, REGIME_HIGH, REGIME_EXTREME)

EVENT_COMPRESSION = "compression"
EVENT_EXPANSION = "expansion"
EVENT_SPIKE = "spike"
EVENT_COLLAPSE = "collapse"


def regime_for_percentile(pct: float) -> str:
    if pct >= 95.0:
        return REGIME_EXTREME
    if pct >= 80.0:
        return REGIME_HIGH
    if pct >= 25.0:
        return REGIME_NORMAL
    return REGIME_LOW


def _rolling_volatility_series(closes: list[float], period: int = _VOL_PERIOD) -> list[float]:
    """realized_volatility recomputed at every point once enough history
    exists -- builds this asset's own recent volatility distribution
    entirely from already-fetched closes, no new persisted time series
    needed. series[-1] is the current reading; series[:-1] is its
    population.
    """
    series = []
    for i in range(period + 1, len(closes) + 1):
        vol = realized_volatility(closes[:i], period=period)
        if vol is not None:
            series.append(vol)
    return series


@dataclass(frozen=True)
class VolatilityReading:
    symbol: str
    available: bool
    realized_vol: float | None = None
    percentile: float | None = None
    regime: str | None = None
    acceleration: float | None = None  # change in realized_vol vs the immediately prior reading
    event_type: str | None = None  # set only when this reading is a genuine regime TRANSITION
    reason: str | None = None


def _classify_transition(previous_regime: str | None, new_regime: str) -> str | None:
    """A transition is only "news" when the regime actually changed. A
    move of exactly one adjacent tier is gradual (EXPANSION/COMPRESSION);
    a jump of two or more tiers in one evaluation is SPIKE/COLLAPSE.
    """
    if previous_regime is None or previous_regime == new_regime:
        return None
    old_index = _REGIME_ORDER.index(previous_regime)
    new_index = _REGIME_ORDER.index(new_regime)
    if new_index > old_index:
        return EVENT_SPIKE if new_index - old_index >= 2 else EVENT_EXPANSION
    return EVENT_COLLAPSE if old_index - new_index >= 2 else EVENT_COMPRESSION


class VolatilityEngine:
    """Reads recent candles, ranks the current realized-volatility reading
    against this asset's own history, and persists a `VolatilityEvent` row
    ONLY on a genuine regime transition -- not every cycle, so
    `volatility_events` stays a log of real changes rather than a periodic
    snapshot table (same "record transitions, not ticks" discipline as
    packages/research/drift.py).
    """

    def analyze(
        self, db: Session, asset_id: int, symbol: str, *, timeframe: str = TIMEFRAME, now: datetime | None = None,
    ) -> VolatilityReading:
        now = now or datetime.now(timezone.utc)
        candles = get_recent_candles(db, asset_id, timeframe, _LOOKBACK_CANDLES)
        closes = [c.close for c in candles]
        series = _rolling_volatility_series(closes)

        if len(candles) < _MIN_CANDLES or len(series) < 2:
            return VolatilityReading(
                symbol=symbol, available=False,
                reason=f"only {len(candles)} candles / {len(series)} volatility readings, need at least {_MIN_CANDLES} candles",
            )

        current = series[-1]
        population = series[:-1]
        pct = percentile_rank(current, population)
        regime = regime_for_percentile(pct)
        acceleration = current - series[-2]

        previous = (
            db.query(VolatilityEvent)
            .filter(VolatilityEvent.asset_id == asset_id, VolatilityEvent.timeframe == timeframe)
            .order_by(VolatilityEvent.ts.desc())
            .first()
        )
        previous_regime = previous.regime if previous is not None else None
        event_type = _classify_transition(previous_regime, regime)

        if event_type is not None:
            db.add(
                VolatilityEvent(
                    asset_id=asset_id, ts=now, timeframe=timeframe, event_type=event_type, realized_vol=current,
                    percentile=pct, regime=regime,
                )
            )
            db.commit()
            logger.info("Volatility %s for asset_id=%s: %s -> %s", event_type, asset_id, previous_regime, regime)

        return VolatilityReading(
            symbol=symbol, available=True, realized_vol=current, percentile=pct, regime=regime,
            acceleration=acceleration, event_type=event_type,
        )
