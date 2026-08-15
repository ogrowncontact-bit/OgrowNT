import pytest

from packages.quant.learning.quarantine import (
    HEALTH_SCORE_QUARANTINE_THRESHOLD,
    evaluate_quarantine,
    restore_from_quarantine,
)
from packages.shared.models import Alert, AuditLog, StrategyPerformance, StrategyRow


def _strategy(db_session, code: str, lifecycle_stage: str = "paper") -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0", lifecycle_stage=lifecycle_stage)
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _perf(strategy_id: int, health_score: float | None, window_trades: int = 10) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_id=strategy_id, window_trades=window_trades, total_trades=window_trades,
        win_rate=0.3, expectancy=-0.5, health_score=health_score,
    )


def test_healthy_strategy_is_not_quarantined(db_session):
    strategy = _strategy(db_session, "healthy_v1")
    quarantined = evaluate_quarantine(db_session, strategy.id, _perf(strategy.id, HEALTH_SCORE_QUARANTINE_THRESHOLD + 10))
    assert quarantined is False
    db_session.refresh(strategy)
    assert strategy.lifecycle_stage == "paper"


def test_unhealthy_strategy_is_quarantined_with_audit_trail(db_session):
    strategy = _strategy(db_session, "unhealthy_v1")
    quarantined = evaluate_quarantine(db_session, strategy.id, _perf(strategy.id, HEALTH_SCORE_QUARANTINE_THRESHOLD - 10))
    assert quarantined is True
    db_session.refresh(strategy)
    assert strategy.lifecycle_stage == "quarantine"

    alert = db_session.query(Alert).filter(Alert.category == "learning").order_by(Alert.id.desc()).first()
    assert alert is not None and "quarantined" in alert.message

    audit = db_session.query(AuditLog).filter(AuditLog.action == "quarantine_strategy").order_by(AuditLog.id.desc()).first()
    assert audit is not None and audit.entity_id == strategy.id


def test_none_health_score_never_quarantines(db_session):
    strategy = _strategy(db_session, "thin_sample_v1")
    quarantined = evaluate_quarantine(db_session, strategy.id, _perf(strategy.id, None))
    assert quarantined is False
    db_session.refresh(strategy)
    assert strategy.lifecycle_stage == "paper"


def test_non_quarantinable_stage_is_left_alone(db_session):
    strategy = _strategy(db_session, "idea_stage_v1", lifecycle_stage="idea")
    quarantined = evaluate_quarantine(db_session, strategy.id, _perf(strategy.id, 0.0))
    assert quarantined is False
    db_session.refresh(strategy)
    assert strategy.lifecycle_stage == "idea"


def test_already_quarantined_strategy_is_not_re_quarantined(db_session):
    strategy = _strategy(db_session, "already_q_v1", lifecycle_stage="quarantine")
    quarantined = evaluate_quarantine(db_session, strategy.id, _perf(strategy.id, 0.0))
    assert quarantined is False


def test_restore_from_quarantine_requires_quarantine_state(db_session):
    strategy = _strategy(db_session, "not_quarantined_v1", lifecycle_stage="paper")
    with pytest.raises(ValueError):
        restore_from_quarantine(db_session, strategy.id)


def test_restore_from_quarantine_moves_back_to_paper_by_default(db_session):
    strategy = _strategy(db_session, "restore_v1", lifecycle_stage="quarantine")
    restored = restore_from_quarantine(db_session, strategy.id)
    assert restored.lifecycle_stage == "paper"

    audit = db_session.query(AuditLog).filter(AuditLog.action == "restore_strategy").order_by(AuditLog.id.desc()).first()
    assert audit is not None and audit.entity_id == strategy.id


def test_restore_rejects_invalid_target_stage(db_session):
    strategy = _strategy(db_session, "restore_bad_v1", lifecycle_stage="quarantine")
    with pytest.raises(ValueError):
        restore_from_quarantine(db_session, strategy.id, to_stage="production_but_typo")
