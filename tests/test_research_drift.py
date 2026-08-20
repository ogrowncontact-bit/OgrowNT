"""Drift Detection — "PROMPT 10" §34-37."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.data.quality import QualityReport
from packages.research import drift
from packages.shared.models import OHLCV, Agent, AgentMessageRow, AgentPrediction, Asset, Pattern, StrategyRow


def test_detect_strategy_drift_insufficient_history(db_session):
    strategy = StrategyRow(code="drift_strategy_v1", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    result = drift.detect_strategy_drift(db_session, strategy_id=strategy.id, entity="strategy:drift_strategy_v1")
    assert result.detected is False
    assert result.severity == drift.SEVERITY_NONE


def test_record_drift_only_persists_when_detected(db_session):
    from packages.shared.models import DriftDetection

    not_detected = drift.DriftResult(drift_type="market", entity="x", detected=False, severity="none", detail={})
    assert drift.record_drift(db_session, not_detected) is None

    detected = drift.DriftResult(drift_type="market", entity="asset:1:1m", detected=True, severity="high", detail={"z_score": 3.0})
    row = drift.record_drift(db_session, detected)
    assert row is not None
    assert row.drift_type == "market"
    reloaded = db_session.get(DriftDetection, row.id)
    assert reloaded is not None


def test_detect_agent_drift_insufficient_predictions(db_session):
    result = drift.detect_agent_drift(db_session, agent_code="nonexistent_agent")
    assert result.detected is False


def test_detect_agent_drift_detects_a_real_accuracy_shift(db_session):
    asset = Asset(symbol="DRIFTAGENTASSET", asset_class="crypto", is_active=True)
    db_session.add(asset)
    agent = Agent(code="drift_agent", name="Drift Agent", directional=True)
    db_session.add(agent)
    db_session.commit()
    message = AgentMessageRow(agent_code="drift_agent", asset_id=asset.id, status="ok", signal="long", confidence=0.7)
    db_session.add(message)
    db_session.commit()

    now = datetime.now(timezone.utc)
    n = 25
    for i in range(n):  # baseline: mostly correct
        db_session.add(
            AgentPrediction(
                agent_code="drift_agent", agent_message_id=message.id, asset_id=asset.id, predicted_direction="long",
                confidence=0.7, reference_price=100.0, predicted_at=now - timedelta(days=20, hours=i),
                evaluate_at=now - timedelta(days=20, hours=i) + timedelta(hours=1),
                outcome="correct" if i % 5 != 0 else "incorrect",
                evaluated_at=now - timedelta(days=20, hours=i) + timedelta(hours=1),
            )
        )
    for i in range(n):  # recent: mostly incorrect
        db_session.add(
            AgentPrediction(
                agent_code="drift_agent", agent_message_id=message.id, asset_id=asset.id, predicted_direction="long",
                confidence=0.7, reference_price=100.0, predicted_at=now - timedelta(hours=i),
                evaluate_at=now - timedelta(hours=i) + timedelta(minutes=30),
                outcome="incorrect" if i % 5 != 0 else "correct",
                evaluated_at=now - timedelta(hours=i) + timedelta(minutes=30),
            )
        )
    db_session.commit()
    result = drift.detect_agent_drift(db_session, agent_code="drift_agent", now=now, recent_window_days=7, baseline_window_days=30)
    assert result.detected is True
    assert result.severity in (drift.SEVERITY_MEDIUM, drift.SEVERITY_HIGH)


def _seed_ohlcv(db_session, asset: Asset, closes: list[float], *, timeframe="1m", start=None):
    start = start or (datetime.now(timezone.utc) - timedelta(minutes=len(closes)))
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(minutes=i), open=close, high=close * 1.001, low=close * 0.999, close=close, volume=100.0)
        )
    db_session.commit()


def test_detect_market_drift_insufficient_sample(db_session):
    asset = Asset(symbol="DRIFTMARKET1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    _seed_ohlcv(db_session, asset, [100.0] * 5)
    result = drift.detect_market_drift(db_session, asset_id=asset.id, timeframe="1m")
    assert result.detected is False


def test_detect_market_drift_detects_a_volatility_shift(db_session):
    asset = Asset(symbol="DRIFTMARKET2", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    now = datetime.now(timezone.utc)
    baseline_start = now - timedelta(days=37)
    baseline_closes = [100.0 * (1 + 0.0005 * ((i % 2) * 2 - 1)) for i in range(30)]  # low vol
    _seed_ohlcv(db_session, asset, baseline_closes, start=baseline_start)

    recent_start = now - timedelta(days=6)
    recent_closes = [100.0 * (1 + 0.05 * ((i % 2) * 2 - 1)) for i in range(30)]  # high vol
    _seed_ohlcv(db_session, asset, recent_closes, start=recent_start)

    result = drift.detect_market_drift(db_session, asset_id=asset.id, timeframe="1m", now=now, recent_window_days=7, baseline_window_days=30)
    assert result.detected is True


def test_detect_feature_drift_insufficient_sample(db_session):
    result = drift.detect_feature_drift(db_session, pattern_type="nonexistent_pattern")
    assert result.detected is False


def test_detect_feature_drift_detects_a_confidence_shift(db_session):
    asset = Asset(symbol="DRIFTPATTERN1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    now = datetime.now(timezone.utc)
    n = 25
    for i in range(n):
        db_session.add(
            Pattern(asset_id=asset.id, timeframe="1m", ts=now - timedelta(days=20, hours=i), pattern_type="drift_pattern", pattern_class="technical", direction="bullish", strength=0.5, confidence=0.9)
        )
    for i in range(n):
        db_session.add(
            Pattern(asset_id=asset.id, timeframe="1m", ts=now - timedelta(hours=i), pattern_type="drift_pattern", pattern_class="technical", direction="bullish", strength=0.5, confidence=0.2)
        )
    db_session.commit()
    result = drift.detect_feature_drift(db_session, pattern_type="drift_pattern", now=now, recent_window_days=7, baseline_window_days=30)
    assert result.detected is True


def test_detect_data_drift_good_quality_is_no_drift():
    report = QualityReport(symbol="BTCUSDT", quality_score=95, status="GOOD", components={})
    result = drift.detect_data_drift(report, entity="asset:BTCUSDT:1m")
    assert result.detected is False
    assert result.severity == drift.SEVERITY_NONE


def test_detect_data_drift_degraded_and_unsafe_are_flagged():
    degraded = QualityReport(symbol="BTCUSDT", quality_score=60, status="DEGRADED", components={})
    result = drift.detect_data_drift(degraded, entity="asset:BTCUSDT:1m")
    assert result.detected is True
    assert result.severity == drift.SEVERITY_MEDIUM

    unsafe = QualityReport(symbol="BTCUSDT", quality_score=10, status="DATA_UNSAFE", components={})
    result2 = drift.detect_data_drift(unsafe, entity="asset:BTCUSDT:1m")
    assert result2.detected is True
    assert result2.severity == drift.SEVERITY_HIGH
