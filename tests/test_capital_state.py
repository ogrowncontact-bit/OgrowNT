from datetime import datetime, timedelta, timezone

import pytest
import yaml

from packages.portfolio.state import refresh_snapshot
from packages.risk.capital_state import (
    CAUTION,
    CRITICAL,
    DEFENSIVE,
    EMERGENCY,
    HIGH_RISK,
    NORMAL,
    assess_drawdown,
    compute_capital_state,
    strategy_drawdown_pct,
)
from packages.risk.config import CONFIG_PATH, load_risk_limits
from packages.shared.models import PortfolioSnapshot, StrategyPerformance, StrategyRow, SystemState, Trade

LIMITS = load_risk_limits()


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def test_compute_capital_state_wraps_portfolio_state(db_session):
    refresh_snapshot(db_session, cash=12000.0)
    state = compute_capital_state(db_session)

    assert state.available_capital == state.portfolio.cash == 12000.0
    assert state.margin_used == 0.0
    assert state.peak_equity >= state.equity
    assert state.risk_state is None  # AdvancedRiskEngine's job to set, not this function's


def test_compute_capital_state_realized_pnl_sums_closed_trades(db_session):
    strategy = _strategy(db_session, "capstate_pnl_strategy")
    from packages.shared.models import Asset, Position

    asset = Asset(symbol="CAPSTATE_PNL", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="closed",
    )
    db_session.add(position)
    db_session.commit()
    db_session.add_all(
        [
            Trade(position_id=position.id, pnl=50.0, outcome="win"),
            Trade(position_id=position.id, pnl=-20.0, outcome="loss"),
        ]
    )
    db_session.commit()

    state = compute_capital_state(db_session)
    assert state.realized_pnl >= 30.0  # other tests sharing this DB may add more trades


def test_compute_capital_state_realized_pnl_ignores_trades_before_reset(db_session):
    strategy = _strategy(db_session, "capstate_reset_strategy")
    from packages.shared.models import Asset, Position

    asset = Asset(symbol="CAPSTATE_RESET", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="closed",
    )
    db_session.add(position)
    db_session.commit()
    old_trade = Trade(position_id=position.id, pnl=99999.0, outcome="win", closed_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    db_session.add(old_trade)
    db_session.commit()

    state_row = db_session.get(SystemState, True) or SystemState(id=True)
    state_row.last_reset_at = datetime.now(timezone.utc)
    db_session.add(state_row)
    db_session.commit()

    state = compute_capital_state(db_session)
    assert state.realized_pnl < 99999.0  # the pre-reset trade must not count


def test_strategy_drawdown_pct_none_without_performance_row(db_session):
    strategy = _strategy(db_session, "capstate_no_perf_strategy")
    assert strategy_drawdown_pct(db_session, strategy.id, portfolio_equity=10000.0) is None


def test_strategy_drawdown_pct_computed_from_strategy_performance(db_session):
    strategy = _strategy(db_session, "capstate_perf_strategy")
    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, window_trades=10, total_trades=10, max_drawdown=500.0,
        )
    )
    db_session.commit()

    pct = strategy_drawdown_pct(db_session, strategy.id, portfolio_equity=10000.0)
    assert pct == 5.0  # 500 / 10000 * 100


def test_strategy_drawdown_pct_none_when_equity_non_positive(db_session):
    strategy = _strategy(db_session, "capstate_zero_equity_strategy")
    db_session.add(StrategyPerformance(strategy_id=strategy.id, window_trades=1, total_trades=1, max_drawdown=10.0))
    db_session.commit()
    assert strategy_drawdown_pct(db_session, strategy.id, portfolio_equity=0.0) is None


def test_assess_drawdown_below_level_1_is_normal(db_session):
    assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=1.0)
    assert assessment.level == 0
    assert assessment.risk_state == NORMAL
    assert assessment.response == "none"
    assert assessment.threshold_pct is None


@pytest.mark.parametrize(
    "drawdown_pct,expected_level,expected_state,expected_response",
    [
        (3.0, 1, CAUTION, "reduce_exposure"),
        (6.0, 2, DEFENSIVE, "reduce_new_positions"),
        (9.0, 3, HIGH_RISK, "highest_quality_only"),
        (12.0, 4, CRITICAL, "block_new_trades"),
        (15.0, 5, EMERGENCY, "close_and_contain"),
        (99.0, 5, EMERGENCY, "close_and_contain"),  # nothing above level 5 without a circuit breaker
    ],
)
def test_assess_drawdown_level_boundaries(db_session, drawdown_pct, expected_level, expected_state, expected_response):
    assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=drawdown_pct)
    assert assessment.level == expected_level
    assert assessment.risk_state == expected_state
    assert assessment.response == expected_response
    assert assessment.threshold_pct == LIMITS.drawdown_levels.ordered()[expected_level - 1].threshold_pct


def test_assess_drawdown_never_reaches_halted(db_session):
    """"PROMPT 12" §61-62: only the Kill Switch / a circuit breaker can
    reach HALTED — DrawdownEngine's ceiling is EMERGENCY, no matter how
    deep the drawdown."""
    assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=1000.0)
    assert assessment.risk_state == EMERGENCY
    assert assessment.risk_state != "halted"


def test_assess_drawdown_recovery_cooldown_holds_the_higher_level(db_session):
    now = datetime.now(timezone.utc)
    # A severe drawdown 5 minutes ago, well inside the 60-minute cooldown window.
    db_session.add(PortfolioSnapshot(ts=now - timedelta(minutes=5), equity=8500.0, cash=8500.0, drawdown_pct=15.0))
    db_session.commit()

    # The instantaneous reading has since recovered to a shallow drawdown...
    assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=1.0, now=now)

    # ...but the effective (cooldown-adjusted) level must still reflect the
    # recent severe drawdown, and recovery_mode must say so honestly.
    assert assessment.drawdown_pct == 1.0
    assert assessment.effective_drawdown_pct >= 15.0
    assert assessment.risk_state == EMERGENCY
    assert assessment.recovery_mode is True


def test_assess_drawdown_no_recovery_mode_when_nothing_to_recover_from(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(PortfolioSnapshot(ts=now - timedelta(minutes=5), equity=10000.0, cash=10000.0, drawdown_pct=1.0))
    db_session.commit()

    assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=1.0, now=now)
    assert assessment.recovery_mode is False
    assert assessment.effective_drawdown_pct == 1.0


def test_load_risk_limits_rejects_non_monotonic_drawdown_levels(tmp_path):
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    raw["drawdown_levels"]["level_2"]["threshold_pct"] = 1  # now less than level_1's 3
    bad_config = tmp_path / "bad_risk_limits.yaml"
    bad_config.write_text(yaml.safe_dump(raw))

    with pytest.raises(ValueError, match="strictly increasing"):
        load_risk_limits(path=bad_config)
