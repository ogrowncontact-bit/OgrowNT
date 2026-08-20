"""Opportunity Type Classification + Fingerprint + Expiration -- "PROMPT 11" §14-15, §20-24."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.multi_timeframe import AGREEMENT, CONFLICT
from packages.market.opportunity_types import (
    BREAKDOWN,
    BREAKOUT,
    EVENT_DRIVEN,
    MEAN_REVERSION,
    MOMENTUM,
    RELATIVE_STRENGTH,
    RELATIVE_WEAKNESS,
    REVERSAL,
    STATISTICAL_ARBITRAGE_CANDIDATE,
    TREND_CONTINUATION,
    VOLATILITY_COMPRESSION,
    VOLATILITY_EXPANSION,
    OpportunityEvidence,
    classify_opportunity_type,
    compute_expiration,
    compute_fingerprint,
)
from packages.market.structure import (
    BREAK_OF_STRUCTURE,
    CHANGE_OF_CHARACTER,
    NO_BREAK,
    STRUCTURE_DOWNTREND,
    STRUCTURE_RANGING,
    STRUCTURE_UPTREND,
)
from packages.market.volatility import EVENT_COLLAPSE, EVENT_SPIKE

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def test_classify_breakout_on_uptrend_break_of_structure():
    result = classify_opportunity_type(OpportunityEvidence(structure=STRUCTURE_UPTREND, break_state=BREAK_OF_STRUCTURE))
    assert result.opportunity_type == BREAKOUT


def test_classify_breakdown_on_downtrend_break_of_structure():
    result = classify_opportunity_type(OpportunityEvidence(structure=STRUCTURE_DOWNTREND, break_state=BREAK_OF_STRUCTURE))
    assert result.opportunity_type == BREAKDOWN


def test_classify_reversal_on_change_of_character():
    result = classify_opportunity_type(OpportunityEvidence(structure=STRUCTURE_UPTREND, break_state=CHANGE_OF_CHARACTER))
    assert result.opportunity_type == REVERSAL


def test_classify_volatility_expansion_on_spike():
    result = classify_opportunity_type(OpportunityEvidence(volatility_event_type=EVENT_SPIKE))
    assert result.opportunity_type == VOLATILITY_EXPANSION


def test_classify_volatility_compression_on_collapse():
    result = classify_opportunity_type(OpportunityEvidence(volatility_event_type=EVENT_COLLAPSE))
    assert result.opportunity_type == VOLATILITY_COMPRESSION


def test_classify_relative_strength_on_high_percentile():
    result = classify_opportunity_type(OpportunityEvidence(relative_strength_percentile=95.0))
    assert result.opportunity_type == RELATIVE_STRENGTH


def test_classify_relative_weakness_on_low_percentile():
    result = classify_opportunity_type(OpportunityEvidence(relative_strength_percentile=3.0))
    assert result.opportunity_type == RELATIVE_WEAKNESS


def test_classify_mean_reversion_at_range_extreme_without_trend_structure():
    result = classify_opportunity_type(OpportunityEvidence(structure=STRUCTURE_RANGING, range_position=95.0))
    assert result.opportunity_type == MEAN_REVERSION


def test_classify_trend_continuation_on_intact_uptrend():
    result = classify_opportunity_type(OpportunityEvidence(structure=STRUCTURE_UPTREND, break_state=NO_BREAK))
    assert result.opportunity_type == TREND_CONTINUATION


def test_classify_momentum_on_multi_timeframe_agreement_alone():
    result = classify_opportunity_type(OpportunityEvidence(timeframe_agreement=AGREEMENT))
    assert result.opportunity_type == MOMENTUM


def test_classify_event_driven_on_news_shock():
    result = classify_opportunity_type(OpportunityEvidence(news_shock=True))
    assert result.opportunity_type == EVENT_DRIVEN


def test_classify_statistical_arbitrage_on_pairs_signal():
    result = classify_opportunity_type(OpportunityEvidence(pairs_signal=True))
    assert result.opportunity_type == STATISTICAL_ARBITRAGE_CANDIDATE


def test_classify_returns_none_with_no_evidence():
    result = classify_opportunity_type(OpportunityEvidence())
    assert result.opportunity_type is None
    assert "no evidence" in result.reason


def test_classify_pairs_signal_outranks_everything_else():
    result = classify_opportunity_type(
        OpportunityEvidence(
            pairs_signal=True, news_shock=True, structure=STRUCTURE_UPTREND, break_state=BREAK_OF_STRUCTURE,
            timeframe_agreement=AGREEMENT,
        )
    )
    assert result.opportunity_type == STATISTICAL_ARBITRAGE_CANDIDATE


def test_classify_news_shock_outranks_structural_evidence():
    result = classify_opportunity_type(
        OpportunityEvidence(news_shock=True, structure=STRUCTURE_UPTREND, break_state=BREAK_OF_STRUCTURE)
    )
    assert result.opportunity_type == EVENT_DRIVEN


def test_classify_trend_continuation_outranks_bare_momentum_agreement():
    result = classify_opportunity_type(
        OpportunityEvidence(structure=STRUCTURE_UPTREND, break_state=NO_BREAK, timeframe_agreement=AGREEMENT)
    )
    assert result.opportunity_type == TREND_CONTINUATION


def test_classify_conflicting_timeframes_alone_yields_no_opportunity():
    result = classify_opportunity_type(OpportunityEvidence(timeframe_agreement=CONFLICT))
    assert result.opportunity_type is None


def test_compute_fingerprint_is_stable_for_the_same_inputs():
    a = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    b = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    assert a == b


def test_compute_fingerprint_differs_by_opportunity_type():
    a = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    b = compute_fingerprint("BTC/USD", MOMENTUM, "long", 50000.0, now=_NOW)
    assert a != b


def test_compute_fingerprint_same_price_bucket_collapses():
    a = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    b = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50010.0, now=_NOW)  # 0.02% away -- same 0.5% bucket
    assert a == b


def test_compute_fingerprint_far_price_bucket_differs():
    a = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    b = compute_fingerprint("BTC/USD", BREAKOUT, "long", 55000.0, now=_NOW)  # 10% away
    assert a != b


def test_compute_fingerprint_differs_across_time_buckets():
    a = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW)
    b = compute_fingerprint("BTC/USD", BREAKOUT, "long", 50000.0, now=_NOW + timedelta(hours=3))
    assert a != b


def test_compute_expiration_uses_the_type_specific_ttl():
    expires = compute_expiration(EVENT_DRIVEN, now=_NOW)
    assert expires == _NOW + timedelta(hours=1)


def test_compute_expiration_falls_back_to_default_ttl_for_unknown_type():
    expires = compute_expiration(None, now=_NOW)
    assert expires == _NOW + timedelta(hours=4)
