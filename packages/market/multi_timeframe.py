"""Multi-Timeframe Engine -- "PROMPT 11" §39-43.

Nothing in this codebase has ever stored a genuinely distinct 5m/15m/1h/
4h/1D bar: apps/worker/scanner.py only ever writes `timeframe="1m"` rows,
and `MockMarketDataProvider.get_recent_candles` actually ignores the
`timeframe` argument for bucketing purposes (every "bar" it returns is
really one minute wide, whatever timeframe string is passed) -- trusting
its higher-timeframe output directly would be a fabricated-data bug, not a
feature. This module builds real higher timeframes the honest way
instead: resampling the actual persisted 1m OHLCV history into 5m/15m/1h/
4h/1D bars (standard open=first/high=max/low=min/close=last/volume=sum
aggregation), and ONLY emitting a bar for a bucket that has a full,
complete set of 1m candles -- a partial trailing bucket is dropped rather
than reported as a real bar built from incomplete data. This also means
this module works unchanged once a real market data provider replaces the
mock, since resampling from real 1m history is always valid.

A fresh deployment (or a short-lived test/dev environment) simply won't
have 1440 minutes of 1m history yet for a 1D reading -- that shows up as
an honest `available=False` on that timeframe, not a fabricated bar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import TIMEFRAME_SECONDS, Candle
from packages.quant.indicators.core import roc
from packages.shared.market_data import get_recent_candles

# "PROMPT 11" §39's named timeframe set.
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1D")

# Direction classification -- closed vocabulary.
TREND_BULLISH = "bullish"
TREND_BEARISH = "bearish"
TREND_NEUTRAL = "neutral"

# A rate-of-change smaller than this (as a fraction) is treated as noise,
# not a real directional lean.
_DIRECTION_THRESHOLD = 0.002

# "PROMPT 11" §43's explicit, never-hidden agreement states.
AGREEMENT = "agreement"
CONFLICT = "timeframe_conflict"
NEUTRAL = "neutral"
INSUFFICIENT_DATA = "insufficient_data"

AGREEMENT_STATES = (AGREEMENT, CONFLICT, NEUTRAL, INSUFFICIENT_DATA)

# How many 1-minute source candles to pull -- enough to resample a full 1D
# bucket (1440 minutes) plus a little headroom, bounded so the query stays
# cheap regardless of how long the system has been running.
_SOURCE_CANDLE_LIMIT = 1500

_BASE_TIMEFRAME_MINUTES = TIMEFRAME_SECONDS["1m"] // 60  # 1


def resample_candles(source: list[Candle], timeframe: str) -> list[Candle]:
    """Aggregate 1m `source` candles (chronological ascending) into
    `timeframe` bars. Only complete buckets are emitted -- see module
    docstring.
    """
    bucket_minutes = TIMEFRAME_SECONDS[timeframe] // 60
    if bucket_minutes <= _BASE_TIMEFRAME_MINUTES:
        return list(source)  # 1m requested -- already at that granularity

    buckets: dict[int, list[Candle]] = {}
    for candle in source:
        minute_index = int(candle.ts.timestamp() // 60)
        bucket_index = minute_index // bucket_minutes
        buckets.setdefault(bucket_index, []).append(candle)

    resampled = []
    for bucket_index in sorted(buckets):
        members = buckets[bucket_index]
        if len(members) < bucket_minutes:
            continue  # incomplete bucket (partial history at either edge) -- dropped, not faked
        members = sorted(members, key=lambda c: c.ts)
        qualities = {c.data_quality for c in members}
        resampled.append(
            Candle(
                ts=datetime.fromtimestamp(bucket_index * bucket_minutes * 60, tz=timezone.utc),
                open=members[0].open,
                high=max(c.high for c in members),
                low=min(c.low for c in members),
                close=members[-1].close,
                volume=sum(c.volume for c in members),
                data_quality="high" if qualities == {"high"} else "degraded",
            )
        )
    return resampled


@dataclass(frozen=True)
class TimeframeReading:
    timeframe: str
    available: bool
    candle_count: int
    direction: str | None = None
    change_pct: float | None = None


@dataclass(frozen=True)
class MultiTimeframeResult:
    asset_id: int
    symbol: str
    readings: tuple[TimeframeReading, ...]
    agreement_state: str
    agreeing_direction: str | None
    reasons: list[str] = field(default_factory=list)


def _classify_direction(closes: list[float]) -> tuple[str, float] | None:
    """Direction + magnitude from rate-of-change, using whatever lookback
    (up to 5 bars) the available history supports. None means genuinely
    not enough bars to say anything, not "no movement."
    """
    period = min(5, len(closes) - 1)
    if period < 1:
        return None
    change = roc(closes, period=period)
    if change is None:
        return None
    if change > _DIRECTION_THRESHOLD:
        return TREND_BULLISH, change
    if change < -_DIRECTION_THRESHOLD:
        return TREND_BEARISH, change
    return TREND_NEUTRAL, change


class MultiTimeframeEngine:
    """Resamples real 1m history into each requested timeframe and reports
    per-timeframe direction plus an explicit cross-timeframe agreement
    state -- never averaged away, per §43.
    """

    def analyze(
        self, db: Session, asset_id: int, symbol: str, *, timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
    ) -> MultiTimeframeResult:
        source = get_recent_candles(db, asset_id, "1m", _SOURCE_CANDLE_LIMIT)

        readings = []
        for tf in timeframes:
            bars = resample_candles(source, tf)
            closes = [c.close for c in bars]
            classification = _classify_direction(closes)
            if classification is None:
                readings.append(TimeframeReading(timeframe=tf, available=False, candle_count=len(bars)))
                continue
            direction, change = classification
            readings.append(
                TimeframeReading(
                    timeframe=tf, available=True, candle_count=len(bars), direction=direction, change_pct=change,
                )
            )

        return self._aggregate(asset_id, symbol, readings)

    @staticmethod
    def _aggregate(asset_id: int, symbol: str, readings: list[TimeframeReading]) -> MultiTimeframeResult:
        available = [r for r in readings if r.available]
        reasons: list[str] = []

        if len(available) < 2:
            return MultiTimeframeResult(
                asset_id=asset_id, symbol=symbol, readings=tuple(readings), agreement_state=INSUFFICIENT_DATA,
                agreeing_direction=None,
                reasons=["fewer than 2 timeframes have enough history to classify a direction"],
            )

        directional = {r.direction for r in available if r.direction != TREND_NEUTRAL}
        if TREND_BULLISH in directional and TREND_BEARISH in directional:
            bullish_tfs = [r.timeframe for r in available if r.direction == TREND_BULLISH]
            bearish_tfs = [r.timeframe for r in available if r.direction == TREND_BEARISH]
            reasons.append(f"bullish on {bullish_tfs}, bearish on {bearish_tfs}")
            return MultiTimeframeResult(
                asset_id=asset_id, symbol=symbol, readings=tuple(readings), agreement_state=CONFLICT,
                agreeing_direction=None, reasons=reasons,
            )

        if directional:
            direction = next(iter(directional))
            reasons.append(f"{len([r for r in available if r.direction == direction])} timeframe(s) agree on {direction}")
            return MultiTimeframeResult(
                asset_id=asset_id, symbol=symbol, readings=tuple(readings), agreement_state=AGREEMENT,
                agreeing_direction=direction, reasons=reasons,
            )

        reasons.append("every timeframe with enough history reads neutral")
        return MultiTimeframeResult(
            asset_id=asset_id, symbol=symbol, readings=tuple(readings), agreement_state=NEUTRAL,
            agreeing_direction=None, reasons=reasons,
        )
