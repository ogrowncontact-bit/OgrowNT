"""Agent reliability, calibration, quarantine — "PROMPT 9" §5-6, §55-59.
Same DET-only, "no penalty without evidence", risk-reducing-direction-only
precedent as packages/quant/learning/strategy_stats.py + quarantine.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.agents import reliability
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.shared.models import OHLCV, Agent, AgentMessageRow, AgentPrediction, Asset, AuditLog


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_agent(db_session, code: str = "momentum") -> Agent:
    agent = Agent(code=code, name=code, directional=True, version="1.0", status="active")
    db_session.add(agent)
    db_session.commit()
    return agent


def test_sync_agents_from_registry_creates_all_18_and_is_idempotent(db_session):
    reliability.sync_agents_from_registry(db_session)
    assert db_session.query(Agent).count() == 18
    reliability.sync_agents_from_registry(db_session)  # second call must not duplicate or reset state
    assert db_session.query(Agent).count() == 18


def test_sync_never_overwrites_an_existing_quarantine(db_session):
    reliability.sync_agents_from_registry(db_session)
    agent = db_session.get(Agent, "momentum")
    agent.status = "quarantined"
    agent.quarantine_reason = "manual test"
    db_session.commit()

    reliability.sync_agents_from_registry(db_session)
    assert db_session.get(Agent, "momentum").status == "quarantined"


def test_record_prediction_is_skipped_for_a_non_directional_signal(db_session):
    agent = _seed_agent(db_session, "sentiment")
    message = AgentMessage(agent_code="sentiment", status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.5)
    row = AgentMessageRow(agent_code=agent.code, status="ok", signal="neutral", confidence=0.5)
    db_session.add(row)
    db_session.commit()
    reliability.record_prediction(db_session, message, row, asset_id=1, reference_price=100.0)
    db_session.commit()
    assert db_session.query(AgentPrediction).count() == 0


def test_record_prediction_is_skipped_without_a_reference_price(db_session):
    agent = _seed_agent(db_session, "momentum")
    message = AgentMessage(agent_code="momentum", status=AgentStatus.OK, signal=AgentSignal.LONG, confidence=0.7)
    row = AgentMessageRow(agent_code=agent.code, status="ok", signal="long", confidence=0.7)
    db_session.add(row)
    db_session.commit()
    reliability.record_prediction(db_session, message, row, asset_id=1, reference_price=None)
    db_session.commit()
    assert db_session.query(AgentPrediction).count() == 0


def test_settle_predictions_marks_correct_when_price_moved_as_predicted(db_session):
    asset = _asset(db_session, "RELCORRECT")
    agent = _seed_agent(db_session, "momentum")
    now = datetime.now(timezone.utc)
    row = AgentMessageRow(agent_code=agent.code, status="ok", signal="long", confidence=0.8, generated_at=now)
    db_session.add(row)
    db_session.commit()
    db_session.add(
        AgentPrediction(
            agent_code=agent.code, agent_message_id=row.id, asset_id=asset.id, predicted_direction="long",
            confidence=0.8, reference_price=100.0, predicted_at=now, evaluate_at=now - timedelta(minutes=1), outcome="pending",
        )
    )
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=now, open=105.0, high=106.0, low=104.0, close=105.0, volume=1000))
    db_session.commit()

    settled = reliability.settle_predictions(db_session, now=now)
    assert settled == 1
    prediction = db_session.query(AgentPrediction).one()
    assert prediction.outcome == "correct"


def test_settle_predictions_marks_incorrect_when_price_moved_against_the_call(db_session):
    asset = _asset(db_session, "RELINCORRECT")
    agent = _seed_agent(db_session, "momentum")
    now = datetime.now(timezone.utc)
    row = AgentMessageRow(agent_code=agent.code, status="ok", signal="long", confidence=0.8, generated_at=now)
    db_session.add(row)
    db_session.commit()
    db_session.add(
        AgentPrediction(
            agent_code=agent.code, agent_message_id=row.id, asset_id=asset.id, predicted_direction="long",
            confidence=0.8, reference_price=100.0, predicted_at=now, evaluate_at=now - timedelta(minutes=1), outcome="pending",
        )
    )
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=now, open=95.0, high=96.0, low=94.0, close=95.0, volume=1000))
    db_session.commit()

    reliability.settle_predictions(db_session, now=now)
    assert db_session.query(AgentPrediction).one().outcome == "incorrect"


def test_settle_predictions_never_guesses_without_a_real_candle(db_session):
    """No candle exists yet at/after evaluate_at -- must stay pending, never
    settled against an interpolated/guessed price."""
    asset = _asset(db_session, "RELPENDING")
    agent = _seed_agent(db_session, "momentum")
    now = datetime.now(timezone.utc)
    row = AgentMessageRow(agent_code=agent.code, status="ok", signal="long", confidence=0.8, generated_at=now)
    db_session.add(row)
    db_session.commit()
    db_session.add(
        AgentPrediction(
            agent_code=agent.code, agent_message_id=row.id, asset_id=asset.id, predicted_direction="long",
            confidence=0.8, reference_price=100.0, predicted_at=now, evaluate_at=now - timedelta(minutes=1), outcome="pending",
        )
    )
    db_session.commit()

    settled = reliability.settle_predictions(db_session, now=now)
    assert settled == 0
    assert db_session.query(AgentPrediction).one().outcome == "pending"


def _settled_prediction(db_session, agent_code: str, asset: Asset, outcome: str, confidence: float) -> None:
    row = AgentMessageRow(agent_code=agent_code, status="ok", signal="long", confidence=confidence)
    db_session.add(row)
    db_session.commit()
    db_session.add(
        AgentPrediction(
            agent_code=agent_code, agent_message_id=row.id, asset_id=asset.id, predicted_direction="long",
            confidence=confidence, reference_price=100.0, evaluate_at=datetime.now(timezone.utc), outcome=outcome,
            outcome_price=105.0 if outcome == "correct" else 95.0, evaluated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()


def test_compute_reliability_is_none_below_the_minimum_sample(db_session):
    asset = _asset(db_session, "RELTHIN")
    agent = _seed_agent(db_session, "momentum")
    for _ in range(reliability.MIN_SAMPLE_FOR_RELIABILITY - 1):
        _settled_prediction(db_session, agent.code, asset, "correct", 0.8)
    assert reliability.compute_reliability(db_session, agent.code) is None


def test_compute_reliability_penalizes_overconfidence_on_wrong_calls(db_session):
    asset = _asset(db_session, "RELOVERCONFIDENT")
    agent = _seed_agent(db_session, "momentum")
    for _ in range(5):
        _settled_prediction(db_session, agent.code, asset, "correct", 0.5)
    for _ in range(6):
        _settled_prediction(db_session, agent.code, asset, "incorrect", 0.95)  # very confident and very wrong

    result = reliability.compute_reliability(db_session, agent.code)
    assert result is not None
    assert result.overconfidence_gap is not None and result.overconfidence_gap > 0
    assert result.reliability_score is not None and result.reliability_score < result.accuracy * 100.0


def test_evaluate_quarantine_demotes_below_threshold_and_writes_audit_log(db_session):
    asset = _asset(db_session, "RELQUARANTINE")
    agent = _seed_agent(db_session, "momentum")
    for _ in range(2):
        _settled_prediction(db_session, agent.code, asset, "correct", 0.5)
    for _ in range(10):
        _settled_prediction(db_session, agent.code, asset, "incorrect", 0.9)

    result = reliability.compute_reliability(db_session, agent.code)
    assert result is not None
    quarantined = reliability.evaluate_quarantine(db_session, agent.code, result)
    assert quarantined
    assert db_session.get(Agent, agent.code).status == "quarantined"
    assert db_session.query(AuditLog).filter(AuditLog.action == "quarantine_agent").count() == 1


def test_restore_from_quarantine_requires_the_agent_to_actually_be_quarantined(db_session):
    import pytest

    agent = _seed_agent(db_session, "momentum")
    with pytest.raises(ValueError):
        reliability.restore_from_quarantine(db_session, agent.code)


def test_restore_from_quarantine_reactivates_and_writes_audit_log(db_session):
    agent = _seed_agent(db_session, "momentum")
    agent.status = "quarantined"
    agent.quarantined_at = datetime.now(timezone.utc)
    agent.quarantine_reason = "test"
    db_session.commit()

    restored = reliability.restore_from_quarantine(db_session, agent.code, actor="admin@example.com")
    assert restored.status == "active"
    assert restored.quarantine_reason is None
    assert db_session.query(AuditLog).filter(AuditLog.action == "restore_agent").count() == 1
