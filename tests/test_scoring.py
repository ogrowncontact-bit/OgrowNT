from packages.quant.scoring.config import Penalties, ScoringConfig, Thresholds, Weights
from packages.quant.scoring.engine import ScoringInputs, compute_score, tier_for

CFG = ScoringConfig(
    weights=Weights(
        technical=0.15, pattern=0.15, regime=0.15, historical_edge=0.15,
        liquidity=0.10, news=0.10, risk_reward=0.15, strategy_performance=0.05,
    ),
    penalties=Penalties(volatility_max=15, correlation_max=15, execution_cost_max=10, drawdown_max=10),
    thresholds=Thresholds(ignore=60, watch=70, possible=80, high_quality=90),
)


def _inputs(**overrides) -> ScoringInputs:
    base = dict(
        technical=100, pattern=100, regime_fit=100, historical_edge=100,
        liquidity=100, news=100, risk_reward=100, strategy_performance=100,
    )
    base.update(overrides)
    return ScoringInputs(**base)


def test_all_max_inputs_yield_100():
    score = compute_score(_inputs(), CFG)
    assert score.final_score == 100.0
    assert score.tier == "exceptional"


def test_all_zero_inputs_yield_0():
    score = compute_score(_inputs(technical=0, pattern=0, regime_fit=0, historical_edge=0,
                                   liquidity=0, news=0, risk_reward=0, strategy_performance=0), CFG)
    assert score.final_score == 0.0
    assert score.tier == "ignore"


def test_penalties_reduce_score_but_never_below_zero():
    score = compute_score(
        _inputs(volatility_penalty=1.0, correlation_penalty=1.0, execution_cost_penalty=1.0, drawdown_penalty=1.0),
        CFG,
    )
    # 100 base - (15+15+10+10) = 50
    assert score.final_score == 50.0
    assert score.volatility_penalty_points == 15.0


def test_score_never_exceeds_100_even_with_overweight_inputs():
    score = compute_score(_inputs(technical=1000), CFG)
    assert score.final_score <= 100.0


def test_tier_boundaries():
    t = CFG.thresholds
    assert tier_for(59.99, t) == "ignore"
    assert tier_for(60.0, t) == "watch"
    assert tier_for(69.99, t) == "watch"
    assert tier_for(70.0, t) == "possible"
    assert tier_for(79.99, t) == "possible"
    assert tier_for(80.0, t) == "high_quality"
    assert tier_for(89.99, t) == "high_quality"
    assert tier_for(90.0, t) == "exceptional"


def test_config_loads_from_repo_yaml():
    from packages.quant.scoring.config import load_scoring_config

    cfg = load_scoring_config()
    assert cfg.weights.technical == 0.15
    assert cfg.thresholds.ignore == 60
