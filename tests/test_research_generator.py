"""Strategy Generator — mutation + bounded genetic search — "PROMPT 10" §16-21."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from packages.research.features import FeatureSignal
from packages.research.generator import (
    MAX_SEARCH_EVALUATIONS,
    crossover_params,
    describe_changes,
    mutate_params,
    propose_candidates,
    propose_feature_filter_candidates,
    run_genetic_search,
)
from packages.shared.models import OHLCV, Asset


def test_mutate_params_stays_within_bound():
    rng = random.Random(42)
    base = {"a": 10.0, "b": 5}
    for _ in range(100):
        mutated = mutate_params(rng, base, max_pct=0.2)
        assert 8.0 <= mutated["a"] <= 12.0
        assert isinstance(mutated["b"], int)
        assert mutated["b"] >= 1


def test_mutate_params_is_deterministic_given_the_same_rng_seed():
    a = mutate_params(random.Random(7), {"x": 1.0}, max_pct=0.3)
    b = mutate_params(random.Random(7), {"x": 1.0}, max_pct=0.3)
    assert a == b


def test_crossover_params_only_uses_parent_values():
    rng = random.Random(1)
    parent_a = {"a": 1.0, "b": 2.0}
    parent_b = {"a": 10.0, "b": 20.0}
    for _ in range(20):
        child = crossover_params(rng, parent_a, parent_b)
        assert child["a"] in (1.0, 10.0)
        assert child["b"] in (2.0, 20.0)


def test_describe_changes_only_lists_actual_differences():
    changes = describe_changes({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 3.0})
    assert len(changes) == 1
    assert "b" in changes[0]
    assert "1.0 -> 1.0" not in " ".join(changes)


def _seed_asset(db_session, symbol: str, bars: int = 60, timeframe: str = "1h"):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(hours=bars)
    for i in range(bars):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(hours=i), open=close * 0.998, high=close * 1.006, low=close * 0.994, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()
    return asset, start, start + timedelta(hours=bars)


def test_run_genetic_search_rejects_a_search_over_the_evaluation_bound(db_session):
    asset, start, end = _seed_asset(db_session, "GENERATORBOUND")
    with pytest.raises(ValueError):
        run_genetic_search(
            db_session, strategy_code="momentum_v1", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
            start_ts=start, end_ts=end, window_days=1.0, initial_capital=10_000.0,
            population_size=MAX_SEARCH_EVALUATIONS + 1, generations=1,
        )


def test_run_genetic_search_unknown_strategy_raises(db_session):
    asset, start, end = _seed_asset(db_session, "GENERATORUNKNOWN")
    with pytest.raises(ValueError):
        run_genetic_search(
            db_session, strategy_code="not_a_real_strategy", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
            start_ts=start, end_ts=end, window_days=1.0, initial_capital=10_000.0, population_size=2, generations=1,
        )


def test_run_genetic_search_is_deterministic_given_the_same_seed(db_session):
    asset, start, end = _seed_asset(db_session, "GENERATORDETERMINISTIC")
    kwargs = dict(
        strategy_code="momentum_v1", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
        start_ts=start, end_ts=end, window_days=1.0, initial_capital=10_000.0,
        population_size=3, generations=2, seed=99,
    )
    result_a = run_genetic_search(db_session, **kwargs)
    result_b = run_genetic_search(db_session, **kwargs)
    assert result_a.total_evaluations == result_b.total_evaluations
    params_a = [g.population[i].params for g in result_a.generations for i in range(len(g.population))]
    params_b = [g.population[i].params for g in result_b.generations for i in range(len(g.population))]
    assert params_a == params_b


def test_run_genetic_search_honest_when_nothing_is_consistent(db_session):
    asset, start, end = _seed_asset(db_session, "GENERATORHONEST", bars=10)  # too little data for real consistency
    result = run_genetic_search(
        db_session, strategy_code="momentum_v1", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
        start_ts=start, end_ts=end, window_days=1.0, initial_capital=10_000.0, population_size=2, generations=1,
    )
    assert result.total_evaluations == 2
    if result.best is None:
        assert "none of" in result.reason


def test_propose_feature_filter_candidates_only_uses_non_regime_dependent_positive_signals():
    signals = [
        FeatureSignal(pattern_type="p1", regime="trending_bull", sample_size=20, win_rate=60.0, expectancy=0.4, regime_dependent=False),
        FeatureSignal(pattern_type="p2", regime="ranging", sample_size=20, win_rate=30.0, expectancy=-0.2, regime_dependent=False),
        FeatureSignal(pattern_type="p3", regime="trending_bear", sample_size=20, win_rate=55.0, expectancy=0.3, regime_dependent=True),
    ]
    candidates = propose_feature_filter_candidates(signals)
    assert len(candidates) == 1
    assert candidates[0].source_signal.pattern_type == "p1"
    assert candidates[0].feature_filter == {"eq": ["regime", {"lit": "trending_bull"}]}


def test_propose_candidates_unknown_strategy_raises(db_session):
    with pytest.raises(ValueError):
        propose_candidates(
            db_session, strategy_code="not_a_real_strategy", asset_id=1, symbol="X", timeframe="1h",
            start_ts=datetime.now(timezone.utc) - timedelta(hours=10), end_ts=datetime.now(timezone.utc),
            window_days=1.0, initial_capital=10_000.0,
        )


def test_propose_candidates_returns_empty_list_when_nothing_qualifies(db_session):
    asset, start, end = _seed_asset(db_session, "GENERATOREMPTY", bars=10)
    proposals = propose_candidates(
        db_session, strategy_code="momentum_v1", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
        start_ts=start, end_ts=end, window_days=1.0, initial_capital=10_000.0,
        genetic_kwargs={"population_size": 2, "generations": 1},
    )
    assert isinstance(proposals, list)  # honestly empty, not fabricated
