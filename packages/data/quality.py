"""Data quality scoring — a 0-100 number derived from the same signals as
the OHLCV.data_quality enum ("high"/"degraded"/"unavailable") and
MarketDataProvider.is_connected(), but finer-grained: /api/market/data-quality
and the dashboard's Market Overview panel want a number they can rank/color,
not just a three-value tag.

Deliberately not stored: it's cheap to recompute from data already on disk
(recent OHLCV rows + provider.is_connected()), so persisting it would just
be another place for it to go stale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from packages.data.validation import stale_after_seconds

# Below this overall score, an asset is DATA_UNSAFE (packages/shared/settings.py's
# market_data_quality_unsafe_threshold) -- callers should not treat its
# latest price as trustworthy enough to act on.
GOOD_THRESHOLD = 85

_CONSISTENCY_SCORE = {"high": 100.0, "degraded": 50.0, "unavailable": 0.0}


@dataclass(frozen=True)
class QualityReport:
    symbol: str
    quality_score: int
    status: str  # "GOOD" | "DEGRADED" | "DATA_UNSAFE"
    components: dict[str, float] = field(default_factory=dict)
    detail: str | None = None


def _freshness_score(latest_ts: datetime | None, timeframe: str, now: datetime) -> float:
    if latest_ts is None:
        return 0.0
    age_seconds = (now - latest_ts).total_seconds()
    stale_after = stale_after_seconds(timeframe)
    if age_seconds <= 0:
        return 100.0
    if age_seconds >= stale_after:
        return 0.0
    return 100.0 * (1 - age_seconds / stale_after)


def _timestamp_accuracy_score(latest_ts: datetime | None, now: datetime) -> float:
    if latest_ts is None or latest_ts.tzinfo is None:
        return 0.0
    return 0.0 if latest_ts > now else 100.0


def compute_quality_score(
    *,
    symbol: str,
    latest_ts: datetime | None,
    timeframe: str,
    candle_count: int,
    expected_count: int,
    last_data_quality: str | None,
    provider_connected: bool,
    now: datetime | None = None,
    unsafe_threshold: int = 50,
) -> QualityReport:
    now = now or datetime.now(timezone.utc)

    if latest_ts is None:
        return QualityReport(
            symbol=symbol, quality_score=0, status="DATA_UNSAFE",
            components={"freshness": 0.0, "completeness": 0.0, "consistency": 0.0,
                        "source_availability": 100.0 if provider_connected else 0.0, "timestamp_accuracy": 0.0},
            detail="no OHLCV data recorded yet",
        )

    components = {
        "freshness": _freshness_score(latest_ts, timeframe, now),
        "completeness": min(100.0, 100.0 * candle_count / expected_count) if expected_count > 0 else 100.0,
        "consistency": _CONSISTENCY_SCORE.get(last_data_quality or "unavailable", 0.0),
        "source_availability": 100.0 if provider_connected else 0.0,
        "timestamp_accuracy": _timestamp_accuracy_score(latest_ts, now),
    }
    score = round(sum(components.values()) / len(components))

    if score < unsafe_threshold:
        status = "DATA_UNSAFE"
    elif score < GOOD_THRESHOLD:
        status = "DEGRADED"
    else:
        status = "GOOD"

    return QualityReport(symbol=symbol, quality_score=score, status=status, components=components)
