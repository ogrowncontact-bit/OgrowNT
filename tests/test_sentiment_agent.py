from datetime import datetime, timedelta, timezone

from apps.worker.sentiment_agent import run_sentiment_shift_cycle
from packages.shared.models import Alert, Asset, NewsEvent, NewsImpact

NOW = datetime.now(timezone.utc)


def _seed_impact(db_session, asset_id: int, sentiment: str, hours_ago: float) -> None:
    event = NewsEvent(
        source="Reuters", published_at=NOW - timedelta(hours=hours_ago), headline=f"H{hours_ago}",
        category="other", sentiment=sentiment,
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(
        news_event_id=event.id, asset_id=asset_id, impact="medium",
        direction="bullish" if "bull" in sentiment else "bearish", confidence=0.6, horizon_hours=12, rationale="t",
    ))
    db_session.commit()


def test_detected_shift_raises_an_alert(db_session):
    asset = Asset(symbol="SENTAGENT1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    for _ in range(4):
        _seed_impact(db_session, asset.id, "bullish", hours_ago=20)
    for _ in range(3):
        _seed_impact(db_session, asset.id, "bearish", hours_ago=0.5)

    summary = run_sentiment_shift_cycle(db_session)
    assert summary["shifts_detected"] >= 1

    alert = db_session.query(Alert).filter(Alert.category == "news").filter(
        Alert.message.like("%Sentiment shift detected for SENTAGENT1%")
    ).first()
    assert alert is not None


def test_no_shift_no_alert(db_session):
    asset = Asset(symbol="SENTAGENT2", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    summary = run_sentiment_shift_cycle(db_session)
    assert summary["shifts_detected"] == 0


def test_does_not_realert_within_cooldown(db_session):
    asset = Asset(symbol="SENTAGENT3", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    for _ in range(4):
        _seed_impact(db_session, asset.id, "bullish", hours_ago=20)
    for _ in range(3):
        _seed_impact(db_session, asset.id, "bearish", hours_ago=0.5)

    first = run_sentiment_shift_cycle(db_session)
    second = run_sentiment_shift_cycle(db_session)
    assert first["shifts_detected"] == 1
    assert second["shifts_detected"] == 0  # still within REALERT_COOLDOWN_HOURS
