"""Liquidity Engine -- "PROMPT 11" §9-10, §71-73."""
from __future__ import annotations

from packages.market.liquidity import (
    TIER_A,
    TIER_B,
    TIER_C,
    UNTRADABLE,
    OrderBookSnapshot,
    percentile_rank,
    score_liquidity,
    tier_for_score,
)


def test_percentile_rank_empty_population_is_honest_neutral():
    assert percentile_rank(100.0, []) == 50.0


def test_percentile_rank_top_of_population():
    assert percentile_rank(100.0, [10.0, 20.0, 100.0]) == 100.0


def test_percentile_rank_bottom_of_population():
    assert percentile_rank(1.0, [10.0, 20.0, 100.0]) == 0.0


def test_tier_for_score_boundaries():
    assert tier_for_score(95.0) == TIER_A
    assert tier_for_score(60.0) == TIER_B
    assert tier_for_score(35.0) == TIER_C
    assert tier_for_score(5.0) == UNTRADABLE


def test_score_liquidity_proxy_source_without_orderbook():
    result = score_liquidity(symbol="BTC/USD", volume_percentile=90.0, data_quality_score=95.0)
    assert result.source == "proxy"
    assert result.tier == TIER_A
    assert "spread" not in result.components


def test_score_liquidity_untradable_when_illiquid_and_low_quality():
    result = score_liquidity(symbol="THIN/USD", volume_percentile=5.0, data_quality_score=10.0)
    assert result.tier == UNTRADABLE


def test_score_liquidity_folds_in_real_orderbook_when_available():
    tight_book = OrderBookSnapshot(bid=100.0, ask=100.02, bid_depth=50_000.0, ask_depth=50_000.0)
    result = score_liquidity(
        symbol="AAPL", volume_percentile=80.0, data_quality_score=90.0, orderbook=tight_book,
        max_spread_bps=50.0, min_depth_multiple=1.0, reference_size=1_000.0,
    )
    assert result.source == "orderbook"
    assert "spread" in result.components and "depth" in result.components
    assert result.components["spread"] > 90.0  # a 2bps spread against a 50bps max


def test_score_liquidity_wide_spread_orderbook_penalizes_score():
    wide_book = OrderBookSnapshot(bid=100.0, ask=101.0, bid_depth=10.0, ask_depth=10.0)
    tight_book = OrderBookSnapshot(bid=100.0, ask=100.02, bid_depth=10.0, ask_depth=10.0)
    wide = score_liquidity(
        symbol="WIDE", volume_percentile=80.0, data_quality_score=90.0, orderbook=wide_book,
        max_spread_bps=50.0, min_depth_multiple=1.0, reference_size=1.0,
    )
    tight = score_liquidity(
        symbol="TIGHT", volume_percentile=80.0, data_quality_score=90.0, orderbook=tight_book,
        max_spread_bps=50.0, min_depth_multiple=1.0, reference_size=1.0,
    )
    assert wide.score < tight.score
