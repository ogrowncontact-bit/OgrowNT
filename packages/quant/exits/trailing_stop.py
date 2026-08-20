"""Trailing Stop — "PROMPT 8" §27-29.

Pure math: given a position's trailing_stop_config, the best price seen
since entry so far (favorable_extreme_price), and the latest price, returns
the new (extreme, stop) pair. A trailing stop only ever moves in the
trader's favor — the same anti-martingale-adjacent discipline as
packages/risk/loss_streak.py: nothing here can make a stop WORSE than it
already was, only tighter.

Three types (§28), matching Position.trailing_stop_config's shape
({"type": ..., "value": float}):
- fixed_distance: stop trails `value` price units behind the extreme.
- percentage: stop trails `value`% of the extreme behind it.
- atr_based: stop trails `value` * ATR(14) behind the extreme — the only
  type that needs recent candles (apps/worker/trade_monitor.py only fetches
  them for positions actually configured with this type, not for every
  open position on every cycle).
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import atr

TRAILING_STOP_TYPES = ("fixed_distance", "percentage", "atr_based")


@dataclass(frozen=True)
class TrailingStopUpdate:
    favorable_extreme_price: float
    new_stop: float
    moved: bool  # True iff new_stop is tighter (more favorable to the trader) than current_stop


def compute_trailing_stop(
    *,
    direction: str,
    current_price: float,
    current_stop: float,
    favorable_extreme_price: float | None,
    config: dict,
    recent_candles: list[Candle] | None = None,
) -> TrailingStopUpdate:
    """`favorable_extreme_price=None` means this is the first check since
    entry — current_price itself seeds the extreme."""
    extreme = favorable_extreme_price if favorable_extreme_price is not None else current_price
    extreme = max(extreme, current_price) if direction == "long" else min(extreme, current_price)

    stop_type = config.get("type")
    value = config.get("value", 0.0)

    if stop_type == "fixed_distance":
        distance = value
    elif stop_type == "percentage":
        distance = extreme * (value / 100)
    elif stop_type == "atr_based":
        atr_value = atr(recent_candles, period=14) if recent_candles else None
        if atr_value is None:
            # Honest fallback (docs/blueprint/00-overview.md's "no
            # hallucinated data"): no real ATR to trail by, so the stop
            # stays exactly where it was rather than guessing a distance.
            return TrailingStopUpdate(favorable_extreme_price=extreme, new_stop=current_stop, moved=False)
        distance = atr_value * value
    else:
        return TrailingStopUpdate(favorable_extreme_price=extreme, new_stop=current_stop, moved=False)

    if distance < 0:
        return TrailingStopUpdate(favorable_extreme_price=extreme, new_stop=current_stop, moved=False)

    if direction == "long":
        candidate_stop = extreme - distance
        new_stop = max(current_stop, candidate_stop)  # only ever ratchets upward
    else:
        candidate_stop = extreme + distance
        new_stop = min(current_stop, candidate_stop)  # only ever ratchets downward

    return TrailingStopUpdate(favorable_extreme_price=extreme, new_stop=new_stop, moved=new_stop != current_stop)
