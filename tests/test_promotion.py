from datetime import datetime, timedelta, timezone

import pytest

from packages.quant.learning.promotion import PromotionCriteria, apply_promotion, evaluate_promotion
from packages.shared.models import Asset, AuditLog, Position, StrategyPerformance, StrategyRow, Trade

_asset_counter = [0]


def _asset(db_session) -> Asset:
    _asset_counter[0] += 1
    asset = Asset(symbol=f"PROMOASSET{_asset_counter[0]}", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset

_LOOSE_CRITERIA = PromotionCriteria(
    min_paper_trades=1, min_paper_days=0, max_drawdown_pct=50, min_expectancy=-10, min_sharpe_like=-10, degradation_tolerance_pct=20,
)
_STRICT_CRITERIA = PromotionCriteria(
    min_paper_trades=30, min_paper_days=30, max_drawdown_pct=10, min_expectancy=0, min_sharpe_like=0.5, degradation_tolerance_pct=20,
)


def _strategy(db_session, code: str, lifecycle_stage: str = "paper") -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0", lifecycle_stage=lifecycle_stage)
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _closed_trade(db_session, strategy: StrategyRow, *, closed_at) -> Trade:
    asset = _asset(db_session)
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="closed", realized_pnl=10.0, exit_reason="target_hit")
    db_session.add(position)
    db_session.commit()
    trade = Trade(position_id=position.id, pnl=10.0, r_multiple=1.0, outcome="win", closed_at=closed_at)
    db_session.add(trade)
    db_session.commit()
    return trade


def _perf(strategy: StrategyRow, **overrides) -> StrategyPerformance:
    defaults = dict(strategy_id=strategy.id, window_trades=30, total_trades=30, win_rate=0.6, profit_factor=1.5, max_drawdown=5.0, expectancy=0.5, sharpe=0.8)
    defaults.update(overrides)
    return StrategyPerformance(**defaults)


def test_wrong_lifecycle_stage_is_never_eligible(db_session):
    strategy = _strategy(db_session, "promo_idea_v1", lifecycle_stage="idea")
    verdict = evaluate_promotion(db_session, strategy.id, _LOOSE_CRITERIA)
    assert verdict.eligible is False
    assert verdict.next_stage is None


def test_no_performance_data_is_not_eligible(db_session):
    strategy = _strategy(db_session, "promo_nodata_v1")
    verdict = evaluate_promotion(db_session, strategy.id, _STRICT_CRITERIA)
    assert verdict.eligible is False
    assert any("no expectancy" in r for r in verdict.reasons)


def test_meeting_all_criteria_is_eligible(db_session):
    strategy = _strategy(db_session, "promo_ready_v1")
    _closed_trade(db_session, strategy, closed_at=datetime.now(timezone.utc) - timedelta(days=40))
    db_session.add(_perf(strategy))
    db_session.commit()

    verdict = evaluate_promotion(db_session, strategy.id, _STRICT_CRITERIA)
    assert verdict.eligible is True
    assert verdict.next_stage == "small_capital"
    assert verdict.reasons == []


def test_insufficient_trades_blocks_promotion(db_session):
    strategy = _strategy(db_session, "promo_fewtrades_v1")
    db_session.add(_perf(strategy, total_trades=3))
    db_session.commit()

    verdict = evaluate_promotion(db_session, strategy.id, _STRICT_CRITERIA)
    assert verdict.eligible is False
    assert any("paper trades" in r for r in verdict.reasons)


def test_negative_expectancy_blocks_promotion(db_session):
    strategy = _strategy(db_session, "promo_negexp_v1")
    _closed_trade(db_session, strategy, closed_at=datetime.now(timezone.utc) - timedelta(days=40))
    db_session.add(_perf(strategy, expectancy=-0.3))
    db_session.commit()

    verdict = evaluate_promotion(db_session, strategy.id, _STRICT_CRITERIA)
    assert verdict.eligible is False
    assert any("expectancy" in r for r in verdict.reasons)


def test_apply_promotion_advances_stage_and_audits(db_session):
    strategy = _strategy(db_session, "promo_apply_v1")
    _closed_trade(db_session, strategy, closed_at=datetime.now(timezone.utc) - timedelta(days=40))
    db_session.add(_perf(strategy))
    db_session.commit()

    updated = apply_promotion(db_session, strategy.id, actor="admin@example.com", criteria=_STRICT_CRITERIA)
    assert updated.lifecycle_stage == "small_capital"

    audit = db_session.query(AuditLog).filter(AuditLog.action == "promote_strategy").order_by(AuditLog.id.desc()).first()
    assert audit is not None and audit.detail["to"] == "small_capital"


def test_apply_promotion_raises_when_not_eligible(db_session):
    strategy = _strategy(db_session, "promo_notready_v1")
    with pytest.raises(ValueError):
        apply_promotion(db_session, strategy.id, actor="admin@example.com", criteria=_STRICT_CRITERIA)


def test_small_capital_promotes_to_production(db_session):
    strategy = _strategy(db_session, "promo_smallcap_v1", lifecycle_stage="small_capital")
    _closed_trade(db_session, strategy, closed_at=datetime.now(timezone.utc) - timedelta(days=40))
    db_session.add(_perf(strategy))
    db_session.commit()

    verdict = evaluate_promotion(db_session, strategy.id, _STRICT_CRITERIA)
    assert verdict.eligible is True
    assert verdict.next_stage == "production"
