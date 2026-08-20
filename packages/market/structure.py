"""Market Structure Engine -- "PROMPT 11" §58-61 (higher-highs/higher-lows/
lower-highs/lower-lows, break of structure, change of character, range
boundaries).

Reuses packages/quant/indicators/core.py::recent_high/recent_low for the
range-boundary reading. The swing-point (fractal pivot) detector and the
structure/break classification below are new -- no local-extrema detector
existed anywhere in this codebase before this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import recent_high, recent_low
from packages.shared.market_data import get_recent_candles

# -- closed vocabulary ----------------------------------------------------
SWING_HIGH = "swing_high"
SWING_LOW = "swing_low"

STRUCTURE_UPTREND = "uptrend"  # HH + HL
STRUCTURE_DOWNTREND = "downtrend"  # LH + LL
STRUCTURE_RANGING = "ranging"  # mixed -- e.g. HH but LL (expanding range)
STRUCTURE_INSUFFICIENT_DATA = "insufficient_data"

BREAK_OF_STRUCTURE = "break_of_structure"  # continuation break, same direction as prevailing structure
CHANGE_OF_CHARACTER = "change_of_character"  # reversal break, opposite direction
NO_BREAK = "no_break"

# How many bars on each side must be strictly lower/higher for a bar to
# count as a swing point -- a small, standard fractal window.
_SWING_LOOKAROUND = 2

TIMEFRAME = "1m"
_DEFAULT_LOOKBACK_CANDLES = 60


@dataclass(frozen=True)
class SwingPoint:
    index: int  # position within the candle list passed to find_swing_points
    kind: str  # SWING_HIGH | SWING_LOW
    price: float
    ts: datetime


@dataclass(frozen=True)
class StructureReading:
    symbol: str
    structure: str
    break_state: str
    swing_points: tuple[SwingPoint, ...]
    range_high: float | None
    range_low: float | None
    reason: str | None = None


def find_swing_points(candles: list[Candle], lookaround: int = _SWING_LOOKAROUND) -> list[SwingPoint]:
    """Simple fractal swing detector over chronologically ascending
    `candles`: bar i is a swing high when its high is the STRICT max within
    [i-lookaround, i+lookaround] (swing low symmetric on lows). Strict
    comparison means a flat top/bottom doesn't produce a run of duplicate
    swing points -- an accepted approximation, not a claim of matching any
    particular charting tool's exact pivot algorithm.
    """
    points: list[SwingPoint] = []
    n = len(candles)
    for i in range(lookaround, n - lookaround):
        window = candles[i - lookaround : i + lookaround + 1]
        this = candles[i]
        if all(this.high > c.high for c in window if c is not this):
            points.append(SwingPoint(index=i, kind=SWING_HIGH, price=this.high, ts=this.ts))
        elif all(this.low < c.low for c in window if c is not this):
            points.append(SwingPoint(index=i, kind=SWING_LOW, price=this.low, ts=this.ts))
    return points


def _classify_structure(swings: list[SwingPoint]) -> tuple[str, list[str]]:
    highs = [s for s in swings if s.kind == SWING_HIGH]
    lows = [s for s in swings if s.kind == SWING_LOW]
    if len(highs) < 2 or len(lows) < 2:
        return STRUCTURE_INSUFFICIENT_DATA, []

    higher_highs = highs[-1].price > highs[-2].price
    lower_highs = highs[-1].price < highs[-2].price
    higher_lows = lows[-1].price > lows[-2].price
    lower_lows = lows[-1].price < lows[-2].price

    notes = []
    notes.append("HH" if higher_highs else "LH" if lower_highs else "equal high")
    notes.append("HL" if higher_lows else "LL" if lower_lows else "equal low")

    if higher_highs and higher_lows:
        return STRUCTURE_UPTREND, notes
    if lower_highs and lower_lows:
        return STRUCTURE_DOWNTREND, notes
    return STRUCTURE_RANGING, notes


def _detect_break(candles: list[Candle], structure: str, swings: list[SwingPoint]) -> str:
    if not candles:
        return NO_BREAK
    highs = [s for s in swings if s.kind == SWING_HIGH]
    lows = [s for s in swings if s.kind == SWING_LOW]
    latest_close = candles[-1].close

    if structure == STRUCTURE_UPTREND:
        if lows and latest_close < lows[-1].price:
            return CHANGE_OF_CHARACTER  # broke below the most recent higher-low -- reversal risk
        if highs and latest_close > highs[-1].price:
            return BREAK_OF_STRUCTURE  # broke above the most recent higher-high -- continuation
    elif structure == STRUCTURE_DOWNTREND:
        if highs and latest_close > highs[-1].price:
            return CHANGE_OF_CHARACTER  # broke above the most recent lower-high -- reversal risk
        if lows and latest_close < lows[-1].price:
            return BREAK_OF_STRUCTURE  # broke below the most recent lower-low -- continuation
    return NO_BREAK


class MarketStructureEngine:
    """Reads recent candles, finds swing points, and reports structure +
    an explicit break state -- never averaged into a single "bullish/
    bearish" number the way multi_timeframe.py's directional readings are;
    structure is reported as its own named state.
    """

    def analyze(
        self, db: Session, asset_id: int, symbol: str, *, timeframe: str = TIMEFRAME,
        lookback: int = _DEFAULT_LOOKBACK_CANDLES,
    ) -> StructureReading:
        candles = get_recent_candles(db, asset_id, timeframe, lookback)
        min_candles = _SWING_LOOKAROUND * 2 + 5  # enough margin to plausibly find 2 highs + 2 lows
        if len(candles) < min_candles:
            return StructureReading(
                symbol=symbol, structure=STRUCTURE_INSUFFICIENT_DATA, break_state=NO_BREAK, swing_points=(),
                range_high=None, range_low=None, reason=f"only {len(candles)} candles, need at least {min_candles}",
            )

        swings = find_swing_points(candles)
        structure, notes = _classify_structure(swings)
        break_state = _detect_break(candles, structure, swings)
        range_lookback = min(20, len(candles))

        return StructureReading(
            symbol=symbol, structure=structure, break_state=break_state, swing_points=tuple(swings),
            range_high=recent_high(candles, lookback=range_lookback),
            range_low=recent_low(candles, lookback=range_lookback),
            reason=", ".join(notes) if notes else None,
        )
