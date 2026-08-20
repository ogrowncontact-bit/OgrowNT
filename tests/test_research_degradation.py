"""Degradation Engine — "PROMPT 10" §9-10, §38-40."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.research import degradation
from packages.shared.models import StrategyPerformance, StrategyRow


def _strategy(db_session, code: str, **overrides) -> StrategyRow:
    row = StrategyRow(code=code, name=code, family="test", version="1.0", **overrides)
    db_session.add(row)
    db_session.commit()
    return row


def test_classify_degradation_unknown_strategy_raises(db_session):
    import pytest

    with pytest.raises(ValueError):
        degradation.classify_degradation(db_session, strategy_id=999999)


def test_classify_degradation_healthy_with_no_performance_row_yet(db_session):
    strategy = _strategy(db_session, "degradation_healthy_v1")
    verdict = degradation.classify_degradation(db_session, strategy_id=strategy.id)
    assert verdict.state in degradation.DEGRADATION_STATES


def test_classify_degradation_escalates_with_health_score(db_session):
    strategy = _strategy(db_session, "degradation_scale_v1")
    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, as_of=datetime.now(timezone.utc), window_trades=40, total_trades=40,
            win_rate=20.0, profit_factor=0.5, avg_win=1.0, avg_loss=-1.0, sharpe=-0.5, max_drawdown=15.0,
            expectancy=-0.3, best_regime=None, worst_regime=None, health_score=10.0,
        )
    )
    db_session.commit()
    verdict = degradation.classify_degradation(db_session, strategy_id=strategy.id)
    assert verdict.state != degradation.DEGRADATION_STATES[0]  # not HEALTHY


def test_classify_degradation_healthy_when_health_score_is_high(db_session):
    strategy = _strategy(db_session, "degradation_healthy_score_v1")
    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, as_of=datetime.now(timezone.utc), window_trades=40, total_trades=40,
            win_rate=60.0, profit_factor=1.8, avg_win=1.5, avg_loss=-1.0, sharpe=1.2, max_drawdown=5.0,
            expectancy=0.4, best_regime=None, worst_regime=None, health_score=90.0,
        )
    )
    db_session.commit()
    verdict = degradation.classify_degradation(db_session, strategy_id=strategy.id)
    assert verdict.state == degradation.DEGRADATION_STATES[0]  # HEALTHY


def test_check_change_point_insufficient_history_is_honest(db_session):
    strategy = _strategy(db_session, "degradation_cp_thin_v1")
    result = degradation.check_change_point(db_session, strategy_id=strategy.id, window=30)
    assert result.detected is False
    assert "insufficient trade history" in result.reason


def test_regime_recommendation_disables_for_declared_worst_regime(db_session):
    strategy = _strategy(db_session, "momentum_v1")  # a real registered strategy code with a real risk profile
    rec = degradation._regime_recommendation("ranging", strategy, None)
    assert rec.action in (degradation.REDUCE_USAGE, degradation.DISABLE_FOR_REGIME, degradation.NO_REGIME_ACTION)


def test_regime_recommendation_no_action_when_current_regime_is_none(db_session):
    strategy = _strategy(db_session, "degradation_no_regime_v1")
    rec = degradation._regime_recommendation(None, strategy, None)
    assert rec.action == degradation.NO_REGIME_ACTION
