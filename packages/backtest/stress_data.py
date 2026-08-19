"""Synthetic shock construction for packages/backtest/stress_test.py's
`gap`, `regime_reversal` and `market_crash` scenarios. Pure, in-memory
`Candle` transforms over a real (already-loaded) candle series — nothing
here ever writes to the `ohlcv` table. See stress_test.py's module
docstring for why: a stress scenario must never mutate data other live
worker cadences read concurrently.
"""
from __future__ import annotations

from dataclasses import replace

from packages.data.connectors.market.base import Candle

DEFAULT_GAP_PCT = -0.08
DEFAULT_CRASH_DROP_PCT = -0.35
CRASH_TAIL_BARS = 20


def apply_gap(candles: list[Candle], gap_pct: float = DEFAULT_GAP_PCT) -> tuple[list[Candle], dict]:
    """A single sharp adverse jump at the window's midpoint: everything from
    the midpoint on is shifted by `gap_pct` (a parallel shift, so the shape
    of subsequent price action is preserved, just at a new, lower base) --
    the visible discontinuity is the one bar where the shift starts."""
    if len(candles) < 4:
        return list(candles), {"applied": False, "reason": "too few candles"}
    mid = len(candles) // 2
    factor = 1 + gap_pct
    shocked = list(candles[:mid])
    for c in candles[mid:]:
        shocked.append(replace(c, open=c.open * factor, high=c.high * factor, low=c.low * factor, close=c.close * factor))
    return shocked, {"applied": True, "gap_pct": gap_pct, "gap_at_index": mid}


def apply_regime_reversal(candles: list[Candle]) -> tuple[list[Candle], dict]:
    """Mirrors the second half of the window around the price at the
    midpoint -- an uptrend becomes a downtrend (or vice versa) with the same
    magnitude of moves, testing whether a strategy tuned to one direction
    survives the opposite one."""
    if len(candles) < 4:
        return list(candles), {"applied": False, "reason": "too few candles"}
    mid = len(candles) // 2
    anchor = candles[mid - 1].close
    shocked = list(candles[:mid])
    for c in candles[mid:]:
        shocked.append(
            replace(
                c, open=2 * anchor - c.open, high=2 * anchor - c.low, low=2 * anchor - c.high, close=2 * anchor - c.close,
            )
        )
    return shocked, {"applied": True, "reversed_at_index": mid, "anchor_price": anchor}


def apply_market_crash(candles: list[Candle], drop_pct: float = DEFAULT_CRASH_DROP_PCT, tail_bars: int = CRASH_TAIL_BARS) -> tuple[list[Candle], dict]:
    """Replaces the window's last `tail_bars` candles with a steady,
    monotonic decline from the real price at that point down to
    `anchor * (1 + drop_pct)` -- a sustained crash tail, not a single spike,
    so the Risk Engine's drawdown-based kill switch has a realistic multi-
    bar sequence to actually react to (§60)."""
    if len(candles) <= tail_bars:
        return list(candles), {"applied": False, "reason": "too few candles for a crash tail"}
    split = len(candles) - tail_bars
    anchor = candles[split - 1].close
    final_price = anchor * (1 + drop_pct)
    shocked = list(candles[:split])
    for i, c in enumerate(candles[split:]):
        progress = (i + 1) / tail_bars
        target_close = anchor + (final_price - anchor) * progress
        # Each bar's own range narrows toward the trend line but keeps a
        # small real wick, rather than collapsing to a flat line.
        bar_range = abs(c.high - c.low) or (target_close * 0.005)
        shocked.append(
            replace(
                c, open=target_close + bar_range * 0.2, high=target_close + bar_range * 0.5,
                low=target_close - bar_range * 0.5, close=target_close,
            )
        )
    return shocked, {"applied": True, "drop_pct": drop_pct, "tail_bars": tail_bars, "anchor_price": anchor, "final_price": final_price}
