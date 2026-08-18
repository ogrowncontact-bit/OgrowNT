"""Candle validation — apps/worker/scanner.py runs every fetched candle
through this before it is ever stored or fed to indicators/strategies.

docs/blueprint's "no hallucinated data" rule extends to raw market data
too: a candle that fails these checks must not silently become a price the
rest of the system trusts. A failure here is recorded as an
INVALID_MARKET_DATA MarketEvent (packages/quant/market/events.py) rather
than being stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import TIMEFRAME_SECONDS, Candle

# A single-bar move beyond this is flagged as an absurd value rather than a
# real price -- generous enough that real volatility spikes (which the
# scanner should surface as VOLATILITY_SPIKE, not reject as garbage) still
# pass, but tight enough to catch obvious feed corruption (a misplaced
# decimal point, a unit mismatch).
MAX_SINGLE_BAR_MOVE_PCT = 0.50

# How many bar-widths old a candle can be before it counts as stale, with a
# floor so very short timeframes don't get an unreasonably tight window --
# same shape as packages/shared/worker_health.py's heartbeat staleness.
STALE_AFTER_BAR_MULTIPLIER = 5
STALE_AFTER_FLOOR_SECONDS = 300

# A timestamp this far in the future is treated as invalid rather than a
# clock-skew fluke worth tolerating silently.
MAX_FUTURE_SKEW_SECONDS = 5


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reasons: list[str] = field(default_factory=list)


def stale_after_seconds(timeframe: str) -> int:
    bar_seconds = TIMEFRAME_SECONDS.get(timeframe, 60)
    return max(STALE_AFTER_BAR_MULTIPLIER * bar_seconds, STALE_AFTER_FLOOR_SECONDS)


def validate_candle(
    candle: Candle,
    *,
    timeframe: str,
    previous_close: float | None = None,
    now: datetime | None = None,
) -> ValidationResult:
    """Pure function: no DB/network access, so it's trivial to unit test
    every rejection path in isolation (tests/test_market_validation.py)."""
    reasons: list[str] = []
    now = now or datetime.now(timezone.utc)

    if candle.ts.tzinfo is None:
        reasons.append("timestamp has no timezone")
    elif candle.ts > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        reasons.append("timestamp is in the future")
    else:
        age_seconds = (now - candle.ts).total_seconds()
        stale_after = stale_after_seconds(timeframe)
        if age_seconds > stale_after:
            reasons.append(f"stale data ({age_seconds:.0f}s old, max {stale_after}s for {timeframe})")

    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        reasons.append("non-positive price")
    if candle.volume < 0:
        reasons.append("negative volume")

    # OHLC coherence -- checked unconditionally; a non-positive price is
    # already flagged above, so any coherence violation just adds detail.
    if candle.high < candle.low:
        reasons.append("high < low")
    if candle.high < candle.open:
        reasons.append("high < open")
    if candle.high < candle.close:
        reasons.append("high < close")
    if candle.low > candle.open:
        reasons.append("low > open")
    if candle.low > candle.close:
        reasons.append("low > close")

    if previous_close is not None and previous_close > 0:
        move_pct = abs(candle.close - previous_close) / previous_close
        if move_pct > MAX_SINGLE_BAR_MOVE_PCT:
            reasons.append(
                f"close moved {move_pct * 100:.1f}% in one bar vs previous close {previous_close} "
                f"(max {MAX_SINGLE_BAR_MOVE_PCT * 100:.0f}%)"
            )

    return ValidationResult(valid=not reasons, reasons=reasons)
