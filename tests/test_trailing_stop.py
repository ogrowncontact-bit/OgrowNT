"""packages/quant/exits/trailing_stop.py — "PROMPT 8" §27-29."""
from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.exits.trailing_stop import compute_trailing_stop


def test_fixed_distance_trails_a_long_upward():
    update = compute_trailing_stop(
        direction="long", current_price=110.0, current_stop=95.0,
        favorable_extreme_price=None, config={"type": "fixed_distance", "value": 5.0},
    )
    assert update.favorable_extreme_price == 110.0
    assert update.new_stop == 105.0  # 110 - 5
    assert update.moved


def test_fixed_distance_never_widens_a_long_stop_on_a_pullback():
    # Price pulls back to 108 after the extreme already reached 112 -- the
    # stop must stay anchored to the extreme (112 - 5 = 107), not follow
    # the pullback down.
    update = compute_trailing_stop(
        direction="long", current_price=108.0, current_stop=107.0,
        favorable_extreme_price=112.0, config={"type": "fixed_distance", "value": 5.0},
    )
    assert update.favorable_extreme_price == 112.0  # extreme unchanged by a pullback
    assert update.new_stop == 107.0  # unchanged -- 112-5=107 is not tighter than current_stop=107
    assert not update.moved


def test_percentage_trails_a_short_downward():
    update = compute_trailing_stop(
        direction="short", current_price=90.0, current_stop=105.0,
        favorable_extreme_price=None, config={"type": "percentage", "value": 5.0},
    )
    assert update.favorable_extreme_price == 90.0
    assert update.new_stop == 94.5  # 90 * 1.05
    assert update.moved


def test_stop_never_loosens_on_a_short_pullback():
    update = compute_trailing_stop(
        direction="short", current_price=92.0, current_stop=94.5,
        favorable_extreme_price=90.0, config={"type": "percentage", "value": 5.0},
    )
    assert update.favorable_extreme_price == 90.0  # extreme unchanged -- 92 is worse than 90 for a short
    assert update.new_stop == 94.5  # unchanged, not loosened to 92*1.05=96.6
    assert not update.moved


def _candles(closes: list[float]) -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [
        Candle(
            ts=now - timedelta(minutes=len(closes) - i),
            open=c, high=c * 1.001, low=c * 0.999, close=c, volume=1000, data_quality="high",
        )
        for i, c in enumerate(closes)
    ]


def test_atr_based_uses_real_atr_and_trails_a_long():
    # A steady, small daily range so ATR is small and predictable in sign
    # (not the exact value -- that's packages/quant/indicators/core.py's
    # own test's job) -- this only checks the trailing-stop wiring uses it.
    closes = [100.0 + (i % 3) * 0.1 for i in range(20)]
    candles = _candles(closes)
    update = compute_trailing_stop(
        direction="long", current_price=110.0, current_stop=95.0,
        favorable_extreme_price=None, config={"type": "atr_based", "value": 2.0}, recent_candles=candles,
    )
    assert update.new_stop < 110.0
    assert update.new_stop > 95.0  # a small ATR shouldn't produce a wider stop than the static one
    assert update.moved


def test_atr_based_with_no_candles_holds_the_stop_rather_than_guessing():
    update = compute_trailing_stop(
        direction="long", current_price=110.0, current_stop=95.0,
        favorable_extreme_price=None, config={"type": "atr_based", "value": 2.0}, recent_candles=None,
    )
    assert update.new_stop == 95.0
    assert not update.moved


def test_unknown_type_is_a_no_op():
    update = compute_trailing_stop(
        direction="long", current_price=110.0, current_stop=95.0,
        favorable_extreme_price=None, config={"type": "bogus", "value": 5.0},
    )
    assert update.new_stop == 95.0
    assert not update.moved
