from packages.risk.config import (
    CapitalConfig,
    DataQualityConfig,
    LiquidityConfig,
    LossLimitsConfig,
    PerTradeConfig,
    PortfolioLimitsConfig,
    RiskLimits,
    SafetyBeltMultipliersConfig,
)
from packages.risk.position_sizing import calculate_position_size

LIMITS = RiskLimits(
    capital=CapitalConfig(initial_paper_capital=10000),
    per_trade=PerTradeConfig(max_risk_pct=1.0, min_risk_reward=1.5),
    portfolio=PortfolioLimitsConfig(
        max_exposure_pct=60, max_single_asset_pct=15, max_correlated_cluster_pct=25, correlation_threshold=0.7
    ),
    loss_limits=LossLimitsConfig(
        max_daily_loss_pct=3, max_weekly_loss_pct=6, max_monthly_loss_pct=10,
        max_strategy_drawdown_pct=10, max_portfolio_drawdown_pct=15,
    ),
    liquidity=LiquidityConfig(max_spread_bps=50, min_orderbook_depth_multiple=3),
    data_quality=DataQualityConfig(max_staleness_seconds=120),
    safety_belt_multipliers=SafetyBeltMultipliersConfig(
        normal=1.0, caution=0.75, defensive=0.5, emergency=0.0, kill_switch=0.0
    ),
)


def _size(**overrides):
    params = dict(
        capital=10000, entry_price=100.0, stop_price=95.0, confidence=1.0,
        volatility_factor=1.0, portfolio_headroom_pct=60.0, correlation_headroom_pct=25.0, limits=LIMITS,
    )
    params.update(overrides)
    return calculate_position_size(**params)


def test_zero_size_on_zero_stop_distance():
    result = _size(stop_price=100.0)
    assert result.quantity == 0.0
    assert result.binding_constraint == "invalid_input"


def test_size_is_bound_by_single_asset_cap():
    # risk budget alone would allow far more than 15% of capital
    result = _size(portfolio_headroom_pct=60.0, correlation_headroom_pct=25.0)
    assert result.binding_constraint == "single_asset_cap"
    assert result.notional == 10000 * 0.15


def test_lower_confidence_never_increases_size():
    full_confidence = _size(confidence=1.0, portfolio_headroom_pct=5.0)
    half_confidence = _size(confidence=0.5, portfolio_headroom_pct=5.0)
    assert half_confidence.quantity <= full_confidence.quantity


def test_higher_volatility_never_increases_size():
    calm = _size(volatility_factor=1.0, portfolio_headroom_pct=5.0)
    volatile = _size(volatility_factor=3.0, portfolio_headroom_pct=5.0)
    assert volatile.quantity <= calm.quantity


def test_negative_headroom_yields_zero_size():
    result = _size(portfolio_headroom_pct=-5.0, correlation_headroom_pct=-5.0)
    assert result.quantity == 0.0
