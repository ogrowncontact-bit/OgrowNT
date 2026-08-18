"""Market Scanner event detection — the raw, real-time surveillance layer
apps/worker/scanner.py runs on every candle, distinct from
packages/quant/patterns (the statistical Pattern Engine that classifies
*setups* for the Opportunity Scoring Engine). These are cheap, immediate
"something just happened" candidates for a dashboard ticker and for the
Pattern/Strategy Engines to consume later -- never trade signals
themselves, and severity/confidence here are heuristic magnitude buckets,
not a statistically validated edge.

Pure functions over a candle window so every detector is trivially unit
testable (tests/test_market_scanner_events.py) without a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import (
    MIN_CANDLES_REQUIRED,
    atr,
    avg_volume,
    realized_volatility,
    recent_high,
    recent_low,
    roc,
    trend_strength,
)

EVENT_PRICE_MOVEMENT = "PRICE_MOVEMENT"
EVENT_VOLUME_SPIKE = "VOLUME_SPIKE"
EVENT_VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
EVENT_BREAKOUT_CANDIDATE = "BREAKOUT_CANDIDATE"
EVENT_MOMENTUM_CHANGE = "MOMENTUM_CHANGE"
EVENT_TREND_CHANGE = "TREND_CHANGE"
EVENT_ANOMALY = "ANOMALY"

SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"

# Magnitude buckets, expressed as a ratio (spike detectors) or absolute
# fraction (price movement) -- ordered LOW..CRITICAL, first match wins from
# the top. Deliberately module constants, not settings: these are detection
# heuristics tuned together, not an operator-facing knob like
# scan_interval_seconds.
_PRICE_MOVE_BUCKETS = [(0.10, SEVERITY_CRITICAL), (0.05, SEVERITY_HIGH), (0.02, SEVERITY_MEDIUM), (0.01, SEVERITY_LOW)]
_RATIO_SPIKE_BUCKETS = [(10.0, SEVERITY_CRITICAL), (5.0, SEVERITY_HIGH), (3.0, SEVERITY_MEDIUM), (2.0, SEVERITY_LOW)]
_BREAKOUT_BUCKETS = [(0.05, SEVERITY_CRITICAL), (0.02, SEVERITY_HIGH), (0.01, SEVERITY_MEDIUM), (0.0, SEVERITY_LOW)]
_ANOMALY_RANGE_ATR_BUCKETS = [(6.0, SEVERITY_CRITICAL), (4.5, SEVERITY_HIGH), (3.5, SEVERITY_MEDIUM), (3.0, SEVERITY_LOW)]


@dataclass(frozen=True)
class MarketEventCandidate:
    event_type: str
    severity: str
    confidence: float  # 0.0-1.0
    price: float
    volume: float
    metadata: dict = field(default_factory=dict)


def _bucket(value: float, buckets: list[tuple[float, str]]) -> str | None:
    for threshold, severity in buckets:
        if value >= threshold:
            return severity
    return None


def _confidence(value: float, buckets: list[tuple[float, str]]) -> float:
    critical_threshold = buckets[0][0]
    return min(1.0, value / critical_threshold) if critical_threshold else 0.0


def detect_events(candles: list[Candle], *, lookback: int = 20) -> list[MarketEventCandidate]:
    """candles must be chronological ascending (oldest first, latest last).
    Returns [] rather than guessing when there isn't enough history yet --
    same DATA_UNAVAILABLE discipline as everywhere else in this codebase."""
    if len(candles) < MIN_CANDLES_REQUIRED:
        return []

    latest = candles[-1]
    prior = candles[:-1]
    closes = [c.close for c in candles]
    prior_closes = closes[:-1]
    events: list[MarketEventCandidate] = []

    # PRICE_MOVEMENT
    prev_close = prior_closes[-1]
    if prev_close > 0:
        pct_change = abs(latest.close - prev_close) / prev_close
        severity = _bucket(pct_change, _PRICE_MOVE_BUCKETS)
        if severity:
            events.append(
                MarketEventCandidate(
                    EVENT_PRICE_MOVEMENT, severity, _confidence(pct_change, _PRICE_MOVE_BUCKETS),
                    latest.close, latest.volume,
                    {"pct_change": round(pct_change, 4), "previous_close": prev_close},
                )
            )

    # VOLUME_SPIKE -- baseline excludes the current bar so it can't dilute itself.
    baseline_volume = avg_volume(prior, lookback)
    if baseline_volume and baseline_volume > 0:
        ratio = latest.volume / baseline_volume
        severity = _bucket(ratio, _RATIO_SPIKE_BUCKETS)
        if severity:
            events.append(
                MarketEventCandidate(
                    EVENT_VOLUME_SPIKE, severity, _confidence(ratio, _RATIO_SPIKE_BUCKETS),
                    latest.close, latest.volume,
                    {"volume_ratio": round(ratio, 2), "baseline_volume": round(baseline_volume, 2)},
                )
            )

    # VOLATILITY_SPIKE -- recent realized vol vs an earlier baseline window.
    # realized_volatility(series, period) needs period+1 closes to produce
    # `period` returns, so each window is sliced one element wider than lookback.
    if len(candles) >= 2 * lookback + 1:
        recent_vol = realized_volatility(closes[-(lookback + 1) :], lookback)
        baseline_vol = realized_volatility(closes[-(2 * lookback + 1) : -lookback], lookback)
        if recent_vol is not None and baseline_vol and baseline_vol > 0:
            ratio = recent_vol / baseline_vol
            severity = _bucket(ratio, _RATIO_SPIKE_BUCKETS)
            if severity:
                events.append(
                    MarketEventCandidate(
                        EVENT_VOLATILITY_SPIKE, severity, _confidence(ratio, _RATIO_SPIKE_BUCKETS),
                        latest.close, latest.volume,
                        {"volatility_ratio": round(ratio, 2), "recent_vol": recent_vol, "baseline_vol": baseline_vol},
                    )
                )

    # BREAKOUT_CANDIDATE -- level excludes the current bar, same reasoning as volume.
    prior_high = recent_high(prior, lookback)
    prior_low = recent_low(prior, lookback)
    if prior_high and latest.close > prior_high:
        beyond_pct = (latest.close - prior_high) / prior_high
        severity = _bucket(beyond_pct, _BREAKOUT_BUCKETS)
        events.append(
            MarketEventCandidate(
                EVENT_BREAKOUT_CANDIDATE, severity or SEVERITY_LOW, _confidence(beyond_pct, _BREAKOUT_BUCKETS),
                latest.close, latest.volume,
                {"direction": "up", "level": prior_high, "beyond_pct": round(beyond_pct, 4)},
            )
        )
    elif prior_low and latest.close < prior_low:
        beyond_pct = (prior_low - latest.close) / prior_low
        severity = _bucket(beyond_pct, _BREAKOUT_BUCKETS)
        events.append(
            MarketEventCandidate(
                EVENT_BREAKOUT_CANDIDATE, severity or SEVERITY_LOW, _confidence(beyond_pct, _BREAKOUT_BUCKETS),
                latest.close, latest.volume,
                {"direction": "down", "level": prior_low, "beyond_pct": round(beyond_pct, 4)},
            )
        )

    # MOMENTUM_CHANGE -- rate-of-change sign flip vs one bar earlier.
    roc_now = roc(closes, 10)
    roc_prev = roc(prior_closes, 10)
    if roc_now is not None and roc_prev is not None and roc_now * roc_prev < 0:
        magnitude = abs(roc_now - roc_prev)
        severity = _bucket(magnitude / 100, _PRICE_MOVE_BUCKETS) or SEVERITY_LOW
        events.append(
            MarketEventCandidate(
                EVENT_MOMENTUM_CHANGE, severity, min(1.0, magnitude / 20),
                latest.close, latest.volume,
                {"roc_now": round(roc_now, 3), "roc_previous": round(roc_prev, 3)},
            )
        )

    # TREND_CHANGE -- trend_strength sign flip vs one bar earlier.
    atr_now = atr(candles, 14)
    atr_prev = atr(prior, 14)
    trend_now = trend_strength(closes, atr_now)
    trend_prev = trend_strength(prior_closes, atr_prev)
    if trend_now is not None and trend_prev is not None and trend_now * trend_prev < 0:
        events.append(
            MarketEventCandidate(
                EVENT_TREND_CHANGE, SEVERITY_MEDIUM, min(1.0, abs(trend_now - trend_prev) / 4),
                latest.close, latest.volume,
                {"trend_strength_now": round(trend_now, 3), "trend_strength_previous": round(trend_prev, 3)},
            )
        )

    # ANOMALY -- this bar's range is statistically huge vs its own recent ATR,
    # yet still passed hard validation (packages/data/validation.py) -- an
    # unusual bar shape worth flagging, not necessarily broken data.
    if atr_now and atr_now > 0:
        bar_range = latest.high - latest.low
        range_atr_ratio = bar_range / atr_now
        severity = _bucket(range_atr_ratio, _ANOMALY_RANGE_ATR_BUCKETS)
        if severity:
            events.append(
                MarketEventCandidate(
                    EVENT_ANOMALY, severity, _confidence(range_atr_ratio, _ANOMALY_RANGE_ATR_BUCKETS),
                    latest.close, latest.volume,
                    {"bar_range": round(bar_range, 6), "atr_14": round(atr_now, 6), "range_atr_ratio": round(range_atr_ratio, 2)},
                )
            )

    return events
