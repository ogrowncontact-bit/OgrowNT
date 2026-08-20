"""Feature research + ablation testing — "PROMPT 10" §22-25."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.quant.strategies import MomentumStrategy
from packages.research import dsl
from packages.research.features import FeatureAblationStrategy, research_feature_signals, run_ablation
from packages.shared.models import OHLCV, Asset, PatternPerformance


def test_research_feature_signals_ignores_thin_samples(db_session):
    db_session.add(PatternPerformance(pattern_type="thin_pattern", regime="trending_bull", sample_size=2, win_rate=90.0, avg_r_multiple=1.0, expectancy=1.0))
    db_session.commit()
    signals = research_feature_signals(db_session, min_sample=8)
    assert all(s.pattern_type != "thin_pattern" for s in signals)


def test_research_feature_signals_flags_regime_dependence(db_session):
    db_session.add(PatternPerformance(pattern_type="flip_pattern", regime="trending_bull", sample_size=20, win_rate=60.0, avg_r_multiple=0.5, expectancy=0.5))
    db_session.add(PatternPerformance(pattern_type="flip_pattern", regime="ranging", sample_size=20, win_rate=30.0, avg_r_multiple=-0.3, expectancy=-0.3))
    db_session.commit()
    signals = research_feature_signals(db_session, min_sample=8)
    flip_signals = [s for s in signals if s.pattern_type == "flip_pattern"]
    assert len(flip_signals) == 2
    assert all(s.regime_dependent for s in flip_signals)


def test_research_feature_signals_consistent_sign_is_not_regime_dependent(db_session):
    db_session.add(PatternPerformance(pattern_type="stable_pattern", regime="trending_bull", sample_size=20, win_rate=60.0, avg_r_multiple=0.5, expectancy=0.5))
    db_session.add(PatternPerformance(pattern_type="stable_pattern", regime="trending_bear", sample_size=20, win_rate=55.0, avg_r_multiple=0.3, expectancy=0.3))
    db_session.commit()
    signals = research_feature_signals(db_session, min_sample=8)
    stable_signals = [s for s in signals if s.pattern_type == "stable_pattern"]
    assert all(not s.regime_dependent for s in stable_signals)


def test_feature_ablation_strategy_delegates_identity_fields():
    base = MomentumStrategy()
    wrapped = FeatureAblationStrategy(base=base, feature_filter=None)
    assert wrapped.code == base.code
    assert wrapped.name == base.name
    assert wrapped.family == base.family
    assert wrapped.best_regimes == base.best_regimes
    assert wrapped.worst_regimes == base.worst_regimes


def _seed_asset(db_session, symbol: str, bars: int = 250, timeframe: str = "15m"):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(minutes=15 * bars)
    for i in range(bars):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(minutes=15 * i), open=close * 0.998,
                high=close * 1.006, low=close * 0.994, close=close, volume=500.0 + (i % 11) * 20, data_quality="high",
            )
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=15 * bars)


def test_run_ablation_rejects_an_invalid_feature_filter(db_session):
    asset, start, end = _seed_asset(db_session, "FEATABLATIONBAD")
    import pytest

    with pytest.raises(dsl.DslValidationError):
        run_ablation(
            db_session, base_strategy=MomentumStrategy(), feature_filter={"gt": ["not_a_real_field", 1]},
            asset_id=asset.id, symbol=asset.symbol, timeframe="15m", start_ts=start, end_ts=end, initial_capital=10_000.0,
        )


def test_run_ablation_end_to_end_on_a_real_trending_dataset(db_session):
    asset, start, end = _seed_asset(db_session, "FEATABLATIONGOOD")
    result = run_ablation(
        db_session, base_strategy=MomentumStrategy(), feature_filter={"gt": ["rsi_14", 50]},
        asset_id=asset.id, symbol=asset.symbol, timeframe="15m", start_ts=start, end_ts=end, initial_capital=10_000.0,
    )
    assert result.without_feature.num_trades >= 0
    assert result.with_feature.num_trades >= 0
    assert result.reason  # always explains itself, never silent
    if result.with_feature.num_trades > 0 and result.without_feature.num_trades > 0:
        assert result.expectancy_delta is not None
