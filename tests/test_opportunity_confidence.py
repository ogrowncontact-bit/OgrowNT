from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import compute_indicators
from packages.quant.patterns.detector import CLASS_TECHNICAL, PatternDetection
from packages.quant.regime.classifier import NewsSignal, classify_regime
from packages.quant.scoring.inputs import compute_opportunity_confidence
from packages.quant.strategies import MarketContext


def _ctx(data_quality="high", n=40) -> MarketContext:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    price = 100.0
    candles = []
    for i in range(n):
        price += 0.5
        candles.append(
            Candle(
                ts=ts + timedelta(minutes=i), open=price - 0.1, high=price + 0.2, low=price - 0.2,
                close=price, volume=100, data_quality=data_quality,
            )
        )
    indicators = compute_indicators(candles)
    regime = classify_regime(candles)
    return MarketContext(asset_id=1, symbol="TEST", timeframe="1m", candles=candles, indicators=indicators, regime=regime)


def test_confidence_is_bounded_0_to_100():
    ctx = _ctx()
    confidence, _ = compute_opportunity_confidence(ctx, [], "long", None, None)
    assert 0.0 <= confidence <= 100.0


def test_confidence_is_distinct_from_and_not_derived_from_score():
    # compute_opportunity_confidence never sees final_score at all -- this
    # just documents that by construction, not by comparing numbers.
    import inspect

    params = inspect.signature(compute_opportunity_confidence).parameters
    assert "score" not in params
    assert "final_score" not in params


def test_degraded_data_quality_lowers_confidence():
    high_quality_ctx = _ctx(data_quality="high")
    degraded_ctx = _ctx(data_quality="degraded")
    high_conf, _ = compute_opportunity_confidence(high_quality_ctx, [], "long", 0.5, 0.5)
    low_conf, _ = compute_opportunity_confidence(degraded_ctx, [], "long", 0.5, 0.5)
    assert low_conf < high_conf


def test_insufficient_history_lowers_confidence_and_is_flagged():
    ctx = _ctx()
    with_history, notes_with = compute_opportunity_confidence(ctx, [], "long", 0.8, 0.8)
    without_history, notes_without = compute_opportunity_confidence(ctx, [], "long", None, None)
    assert without_history < with_history
    assert notes_without["insufficient_history"] is True
    assert notes_with["insufficient_history"] is False


def test_aligned_pattern_confidence_propagates():
    ctx = _ctx()
    high_confidence_pattern = PatternDetection("momentum", CLASS_TECHNICAL, "bullish", 0.9, 1.0, {})
    low_confidence_pattern = PatternDetection("momentum", CLASS_TECHNICAL, "bullish", 0.9, 0.1, {})

    high, _ = compute_opportunity_confidence(ctx, [high_confidence_pattern], "long", 0.5, 0.5)
    low, _ = compute_opportunity_confidence(ctx, [low_confidence_pattern], "long", 0.5, 0.5)
    assert low < high


def test_conflicting_pattern_does_not_contribute_its_confidence():
    ctx = _ctx()
    # bearish pattern conflicts with a long signal -- its (high) confidence
    # must not be used, since it isn't the pattern backing this signal.
    conflicting = PatternDetection("momentum", CLASS_TECHNICAL, "bearish", 0.9, 1.0, {})
    no_pattern, _ = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5)
    with_conflicting, _ = compute_opportunity_confidence(ctx, [conflicting], "long", 0.5, 0.5)
    assert no_pattern == with_conflicting


def test_conflicting_news_lowers_confidence_and_is_flagged():
    # Prompt 6 §28: TECHNICAL=BULLISH vs NEWS=BEARISH -> reduced confidence,
    # not a block and not a flipped signal.
    ctx = _ctx()
    bearish_news = [NewsSignal(direction="bearish", impact="high", confidence=0.9)]
    no_news, notes_no_news = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5)
    with_conflict, notes_conflict = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5, news_signals=bearish_news)
    assert with_conflict < no_news
    assert notes_conflict["news_conflict"] is True
    assert notes_no_news["news_conflict"] is False


def test_aligned_news_does_not_lower_confidence():
    ctx = _ctx()
    bullish_news = [NewsSignal(direction="bullish", impact="high", confidence=0.9)]
    no_news, _ = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5)
    with_aligned, notes = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5, news_signals=bullish_news)
    assert with_aligned == no_news
    assert notes["news_conflict"] is False
