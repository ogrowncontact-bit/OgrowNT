from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import compute_indicators
from packages.quant.patterns.detector import CLASS_TECHNICAL, PatternDetection
from packages.quant.regime.classifier import NewsSignal, classify_regime
from packages.quant.scoring.inputs import build_scoring_inputs
from packages.quant.strategies import MarketContext, TrendFollowingStrategy


def _ctx() -> MarketContext:
    ts = datetime.now(timezone.utc) - timedelta(minutes=60)
    price = 100.0
    candles = []
    for i in range(60):
        price += 0.5
        candles.append(Candle(ts=ts + timedelta(minutes=i), open=price - 0.1, high=price + 0.2, low=price - 0.2, close=price, volume=100))
    indicators = compute_indicators(candles)
    regime = classify_regime(candles)
    return MarketContext(asset_id=1, symbol="TEST", timeframe="1m", candles=candles, indicators=indicators, regime=regime)


def _signal_and_analysis(ctx, strategy=None):
    strategy = strategy or TrendFollowingStrategy()
    analysis = strategy.analyze(ctx)
    signal = strategy.generate_signal(ctx)
    assert signal is not None
    return strategy, analysis, signal


def test_pattern_neutral_when_none_detected():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[])
    assert inputs.pattern == 50.0
    assert inputs.notes["pattern"]["pattern_detected"] is False


def test_pattern_boosts_score_when_aligned():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)  # signal.direction == "long"
    aligned = PatternDetection("momentum", CLASS_TECHNICAL, "bullish", 1.0, 1.0, {})
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[aligned], news_signals=[])
    assert inputs.pattern == 100.0
    assert inputs.notes["pattern"]["aligned"] is True


def test_pattern_penalizes_score_when_conflicting():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)  # long signal
    conflicting = PatternDetection("mean_reversion", CLASS_TECHNICAL, "bearish", 1.0, 1.0, {})
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[conflicting], news_signals=[])
    assert inputs.pattern == 0.0
    assert inputs.notes["pattern"]["aligned"] is False


def test_neutral_direction_pattern_does_not_move_score():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    neutral = PatternDetection("volatility", "statistical", "neutral", 1.0, 1.0, {})
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[neutral], news_signals=[])
    assert inputs.pattern == 50.0


def test_news_neutral_with_no_signals():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[])
    assert inputs.news == 50.0
    assert inputs.notes["news"]["news_count"] == 0


def test_high_confidence_aligned_news_boosts_score():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)  # long
    bullish_news = NewsSignal(direction="bullish", impact="high", confidence=0.9)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[bullish_news])
    assert inputs.news == 95.0  # 50 + 1.0(high) * 0.9(confidence) * 50


def test_conflicting_news_penalizes_score():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)  # long
    bearish_news = NewsSignal(direction="bearish", impact="high", confidence=0.9)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[bearish_news])
    assert inputs.news == 5.0


def test_low_impact_news_moves_score_less_than_high_impact():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    low = NewsSignal(direction="bullish", impact="low", confidence=0.9)
    high = NewsSignal(direction="bullish", impact="high", confidence=0.9)
    low_inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[low])
    high_inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[high])
    assert low_inputs.news < high_inputs.news


def test_historical_edge_neutral_when_no_learning_data():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[])
    assert inputs.historical_edge == 50.0
    # Prompt 3 §18: no sample yet is flagged explicitly (INSUFFICIENT_HISTORY),
    # not just silently folded into a neutral score.
    assert inputs.notes["historical_edge"] == {
        "pattern_expectancy": None, "strategy_expectancy": None, "insufficient_history": True,
    }


def test_historical_edge_rises_with_positive_expectancy():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(
        ctx, strategy, analysis, signal, patterns=[], news_signals=[],
        pattern_expectancy=2.0, strategy_expectancy=2.0,
    )
    assert inputs.historical_edge == 100.0  # both halves saturate at +2R


def test_historical_edge_falls_with_negative_expectancy():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(
        ctx, strategy, analysis, signal, patterns=[], news_signals=[],
        pattern_expectancy=-2.0, strategy_expectancy=-2.0,
    )
    assert inputs.historical_edge == 0.0


def test_historical_edge_blends_pattern_and_strategy_halves():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(
        ctx, strategy, analysis, signal, patterns=[], news_signals=[],
        pattern_expectancy=2.0, strategy_expectancy=None,  # only one half has data
    )
    assert inputs.historical_edge == 75.0  # (100 + 50) / 2


def test_strategy_performance_neutral_without_health_score():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=[], news_signals=[])
    assert inputs.strategy_performance == 50.0


def test_strategy_performance_uses_health_score_directly():
    ctx = _ctx()
    strategy, analysis, signal = _signal_and_analysis(ctx)
    inputs = build_scoring_inputs(
        ctx, strategy, analysis, signal, patterns=[], news_signals=[], strategy_health_score=82.5,
    )
    assert inputs.strategy_performance == 82.5
    assert inputs.notes["strategy_performance"] == {"health_score": 82.5}
