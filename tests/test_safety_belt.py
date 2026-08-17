from datetime import datetime, timezone

from packages.portfolio.state import PortfolioState
from packages.risk.config import (
    CapitalConfig,
    DataQualityConfig,
    LiquidityConfig,
    LossLimitsConfig,
    PerTradeConfig,
    PortfolioLimitsConfig,
    RiskLimits,
)
from packages.risk.safety_belt import (
    CAUTION,
    DEFENSIVE,
    EMERGENCY,
    NORMAL,
    evaluate_safety_belt,
    policy_for,
    should_trigger_kill_switch,
    tier_meets_floor,
)

LIMITS = RiskLimits(
    capital=CapitalConfig(initial_paper_capital=10000),
    per_trade=PerTradeConfig(max_risk_pct=1.0, min_risk_reward=1.5),
    portfolio=PortfolioLimitsConfig(
        max_exposure_pct=60, max_single_asset_pct=15, max_correlated_cluster_pct=25, correlation_threshold=0.7
    ),
    loss_limits=LossLimitsConfig(
        max_daily_loss_pct=3, max_weekly_loss_pct=6, max_strategy_drawdown_pct=10, max_portfolio_drawdown_pct=15
    ),
    liquidity=LiquidityConfig(max_spread_bps=50, min_orderbook_depth_multiple=3),
    data_quality=DataQualityConfig(max_staleness_seconds=120),
)


def _state(**overrides) -> PortfolioState:
    base = dict(
        ts=datetime.now(timezone.utc), cash=10000, equity=10000, exposure_pct=0.0,
        daily_pnl=0.0, daily_loss_pct=0.0, weekly_loss_pct=0.0, drawdown_pct=0.0,
        unrealized_pnl=0.0, open_positions=[],
    )
    base.update(overrides)
    return PortfolioState(**base)


def test_normal_when_nothing_is_wrong():
    assert evaluate_safety_belt(_state(), LIMITS) == NORMAL


def test_caution_when_weekly_loss_approaches_limit():
    # 0.7 * max_weekly_loss_pct(6) = 4.2
    assert evaluate_safety_belt(_state(weekly_loss_pct=4.5), LIMITS) == CAUTION


def test_defensive_when_daily_loss_at_limit():
    assert evaluate_safety_belt(_state(daily_loss_pct=3.0), LIMITS) == DEFENSIVE


def test_emergency_when_drawdown_at_limit():
    assert evaluate_safety_belt(_state(drawdown_pct=15.0), LIMITS) == EMERGENCY


def test_emergency_takes_priority_over_lesser_breaches():
    state = _state(drawdown_pct=16.0, daily_loss_pct=3.0, weekly_loss_pct=6.0)
    assert evaluate_safety_belt(state, LIMITS) == EMERGENCY


def test_kill_switch_trigger_is_well_past_emergency():
    # exactly at EMERGENCY threshold should NOT trigger kill switch
    assert not should_trigger_kill_switch(_state(drawdown_pct=15.0), LIMITS)
    # 1.5x the threshold should
    assert should_trigger_kill_switch(_state(drawdown_pct=22.5), LIMITS)


def test_policy_progressively_restricts_size_and_tier_floor():
    normal, caution, defensive = policy_for(NORMAL), policy_for(CAUTION), policy_for(DEFENSIVE)
    assert normal.size_multiplier == 1.0
    assert caution.size_multiplier < normal.size_multiplier
    assert defensive.size_multiplier < caution.size_multiplier
    assert defensive.allow_new_trades
    assert not policy_for(EMERGENCY).allow_new_trades


def test_tier_meets_floor_ordering():
    assert tier_meets_floor("exceptional", "possible")
    assert tier_meets_floor("possible", "possible")
    assert not tier_meets_floor("watch", "possible")
    assert not tier_meets_floor("ignore", "watch")
