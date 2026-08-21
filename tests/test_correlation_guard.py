from datetime import datetime, timedelta, timezone

from packages.risk.config import (
    CapitalConfig,
    DataQualityConfig,
    DrawdownLevelConfig,
    DrawdownLevelsConfig,
    LeverageConfig,
    LiquidityConfig,
    LossLimitsConfig,
    LossStreakConfig,
    NewsRiskMultipliersConfig,
    PerTradeConfig,
    PortfolioLimitsConfig,
    PositionRiskPolicyConfig,
    RecoveryConfig,
    RiskLimits,
    SafetyBeltMultipliersConfig,
)
from packages.risk.correlation_guard import check_correlation_guard, compute_correlation
from packages.shared.models import OHLCV, Asset, Position, StrategyRow

LIMITS = RiskLimits(
    capital=CapitalConfig(initial_paper_capital=10000),
    per_trade=PerTradeConfig(max_risk_pct=1.0, min_risk_reward=1.5),
    portfolio=PortfolioLimitsConfig(
        max_exposure_pct=60, max_single_asset_pct=15, max_correlated_cluster_pct=25, correlation_threshold=0.7,
        max_strategy_allocation_pct=30,
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
    news_risk_multipliers=NewsRiskMultipliersConfig(normal=1.0, elevated=0.75, high=0.5, critical=0.0),
    leverage=LeverageConfig(max_leverage=1.0),
    loss_streak=LossStreakConfig(threshold=5, size_multiplier_when_triggered=0.5),
    position_risk_policy=PositionRiskPolicyConfig(
        regime_change="close", news_risk="reduce", portfolio_emergency="close", reduce_fraction=0.5
    ),
    drawdown_levels=DrawdownLevelsConfig(
        level_1=DrawdownLevelConfig(threshold_pct=3, response="reduce_exposure"),
        level_2=DrawdownLevelConfig(threshold_pct=6, response="reduce_new_positions"),
        level_3=DrawdownLevelConfig(threshold_pct=9, response="highest_quality_only"),
        level_4=DrawdownLevelConfig(threshold_pct=12, response="block_new_trades"),
        level_5=DrawdownLevelConfig(threshold_pct=15, response="close_and_contain"),
    ),
    recovery=RecoveryConfig(cooldown_minutes=60),
)


def _seed_series(db_session, symbol: str, closes: list[float]) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    ts = datetime.now(timezone.utc) - timedelta(minutes=len(closes))
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe="1m", ts=ts + timedelta(minutes=i), open=close, high=close + 0.1, low=close - 0.1, close=close, volume=100)
        )
    db_session.commit()
    return asset


def test_identical_series_are_perfectly_correlated(db_session):
    closes = [100 + i * 0.5 for i in range(40)]
    a = _seed_series(db_session, "CORRA", closes)
    b = _seed_series(db_session, "CORRB", closes)
    corr = compute_correlation(db_session, a.id, b.id)
    assert corr is not None
    assert corr > 0.99


def test_inverse_series_are_negatively_correlated(db_session):
    # B's return at each step is the exact negative of A's return at that
    # step -- a real mirror image, not just "one goes up while one goes
    # down" (two straight lines in opposite directions are actually
    # *positively* correlated in returns-space, since both have a
    # monotonic, same-signed trend in their return series).
    import random

    rng = random.Random(42)
    closes_a = [100.0]
    for _ in range(39):
        closes_a.append(closes_a[-1] * (1 + rng.uniform(-0.02, 0.02)))
    closes_b = [200.0]
    for i in range(1, 40):
        step_return = (closes_a[i] - closes_a[i - 1]) / closes_a[i - 1]
        closes_b.append(closes_b[-1] * (1 - step_return))

    a = _seed_series(db_session, "CORRC", closes_a)
    b = _seed_series(db_session, "CORRD", closes_b)
    corr = compute_correlation(db_session, a.id, b.id)
    assert corr is not None
    assert corr < -0.99


def test_correlation_none_with_insufficient_history(db_session):
    a = _seed_series(db_session, "CORRE", [100.0, 101.0])
    b = _seed_series(db_session, "CORRF", [50.0, 51.0])
    assert compute_correlation(db_session, a.id, b.id) is None


def test_guard_blocks_when_correlated_cluster_exceeds_limit(db_session):
    closes = [100 + i * 0.5 for i in range(40)]
    asset_a = _seed_series(db_session, "CLUSTA", closes)
    asset_b = _seed_series(db_session, "CLUSTB", closes)  # perfectly correlated with A

    strategy = StrategyRow(code="guard_test_strategy", name="Guard Test", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    open_position = Position(
        asset_id=asset_a.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, current_stop=95.0, size=20.0, status="open",  # 2000 notional = 20% of 10k equity
    )
    db_session.add(open_position)
    db_session.commit()

    # Candidate on asset_b (correlated with A) wanting another 10% -> 30% > 25% cluster limit
    result = check_correlation_guard(db_session, asset_b.id, 10.0, [open_position], equity=10000.0, limits=LIMITS)
    assert result.blocked
    assert result.reason == "correlated_cluster_exceeded"
    assert len(result.correlated_positions) == 1


def test_guard_allows_uncorrelated_positions(db_session):
    closes_a = [100 + i * 0.5 for i in range(40)]
    closes_b = [50 + ((-1) ** i) * 0.3 for i in range(40)]  # noisy, unrelated to a's steady climb
    asset_a = _seed_series(db_session, "UNCORRA", closes_a)
    asset_b = _seed_series(db_session, "UNCORRB", closes_b)

    strategy = StrategyRow(code="guard_test_strategy_2", name="Guard Test 2", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    open_position = Position(
        asset_id=asset_a.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, current_stop=95.0, size=20.0, status="open",
    )
    db_session.add(open_position)
    db_session.commit()

    result = check_correlation_guard(db_session, asset_b.id, 10.0, [open_position], equity=10000.0, limits=LIMITS)
    assert not result.blocked
