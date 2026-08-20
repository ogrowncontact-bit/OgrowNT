"""Market Structure Engine -- "PROMPT 11" §58-61."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import packages.market.structure as structure_mod
from packages.data.connectors.market.base import Candle
from packages.market.structure import (
    BREAK_OF_STRUCTURE,
    CHANGE_OF_CHARACTER,
    NO_BREAK,
    STRUCTURE_DOWNTREND,
    STRUCTURE_INSUFFICIENT_DATA,
    STRUCTURE_UPTREND,
    MarketStructureEngine,
    SwingPoint,
    find_swing_points,
)
from packages.shared.models import OHLCV, Asset

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)

# A hand-verified zigzag: swing high at index 4 (50), swing low at index 7
# (20), swing high at index 11 (60, > 50 -> HH), swing low at index 14 (30,
# > 20 -> HL). No other index in [2, 14] satisfies the strict fractal test.
_ZIGZAG_VALUES = [10, 20, 30, 40, 50, 40, 30, 20, 25, 35, 45, 60, 45, 35, 30, 35, 40]


def _flat_candles(values: list[float]) -> list[Candle]:
    return [
        Candle(ts=_START + timedelta(minutes=i), open=v, high=v, low=v, close=v, volume=10.0, data_quality="high")
        for i, v in enumerate(values)
    ]


def test_find_swing_points_matches_hand_verified_zigzag():
    candles = _flat_candles(_ZIGZAG_VALUES)
    swings = find_swing_points(candles)
    assert [(s.index, s.kind, s.price) for s in swings] == [
        (4, "swing_high", 50.0),
        (7, "swing_low", 20.0),
        (11, "swing_high", 60.0),
        (14, "swing_low", 30.0),
    ]


def test_classify_structure_uptrend_on_higher_highs_and_higher_lows():
    swings = find_swing_points(_flat_candles(_ZIGZAG_VALUES))
    structure, notes = structure_mod._classify_structure(swings)
    assert structure == STRUCTURE_UPTREND
    assert "HH" in notes and "HL" in notes


def test_classify_structure_downtrend_on_lower_highs_and_lower_lows():
    # Negating the hand-verified zigzag flips every local max into a local
    # min and vice versa at the same indices, which flips HH+HL into LH+LL.
    down_values = [-v for v in _ZIGZAG_VALUES]
    swings = find_swing_points(_flat_candles(down_values))
    highs = [s for s in swings if s.kind == "swing_high"]
    lows = [s for s in swings if s.kind == "swing_low"]
    assert len(highs) >= 2 and len(lows) >= 2
    structure, notes = structure_mod._classify_structure(swings)
    assert structure == STRUCTURE_DOWNTREND
    assert "LH" in notes and "LL" in notes


def test_classify_structure_insufficient_data_with_too_few_swings():
    structure, notes = structure_mod._classify_structure([SwingPoint(index=0, kind="swing_high", price=1.0, ts=_START)])
    assert structure == STRUCTURE_INSUFFICIENT_DATA
    assert notes == []


def test_detect_break_of_structure_when_uptrend_close_breaks_above_last_high():
    candles = _flat_candles(_ZIGZAG_VALUES + [70.0])  # closes above the last swing high (60)
    swings = find_swing_points(candles)
    structure, _ = structure_mod._classify_structure(swings)
    assert structure == STRUCTURE_UPTREND
    assert structure_mod._detect_break(candles, structure, swings) == BREAK_OF_STRUCTURE


def test_detect_change_of_character_when_uptrend_close_breaks_below_last_low():
    candles = _flat_candles(_ZIGZAG_VALUES + [15.0])  # closes below the last swing low (30)
    swings = find_swing_points(candles)
    structure, _ = structure_mod._classify_structure(swings)
    assert structure == STRUCTURE_UPTREND
    assert structure_mod._detect_break(candles, structure, swings) == CHANGE_OF_CHARACTER


def test_detect_no_break_when_close_stays_within_structure():
    candles = _flat_candles(_ZIGZAG_VALUES)  # ends at 40, between last low (30) and last high (60)
    swings = find_swing_points(candles)
    structure, _ = structure_mod._classify_structure(swings)
    assert structure_mod._detect_break(candles, structure, swings) == NO_BREAK


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def test_engine_analyze_reports_insufficient_data_with_too_few_candles(db_session):
    asset = _asset(db_session, "STRUCT_THIN")
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=_START, open=1, high=1, low=1, close=1, volume=1, data_quality="high")
    )
    db_session.commit()
    result = MarketStructureEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.structure == STRUCTURE_INSUFFICIENT_DATA
    assert result.swing_points == ()


def test_engine_analyze_end_to_end_against_real_db_candles(db_session):
    asset = _asset(db_session, "STRUCT_E2E")
    for i, v in enumerate(_ZIGZAG_VALUES):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=v, high=v, low=v, close=v,
                volume=10.0, data_quality="high",
            )
        )
    db_session.commit()

    result = MarketStructureEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.structure == STRUCTURE_UPTREND
    assert result.break_state == NO_BREAK
    assert len(result.swing_points) == 4
    assert result.range_high is not None and result.range_low is not None
