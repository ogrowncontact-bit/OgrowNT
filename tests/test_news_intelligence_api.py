from datetime import datetime, timedelta, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Asset, MacroEvent, NewsEvent, NewsImpact


def _login(client, db_session, email="newsintel-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_list_news_includes_intelligence_fields(client, db_session):
    asset = Asset(symbol="NEWSINTEL1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    event = NewsEvent(
        source="Reuters", published_at=datetime.now(timezone.utc), headline="Intelligence fields test",
        category="crypto", source_quality_score=95.0, sentiment="bullish", sentiment_confidence=0.75,
        importance="high", novelty_score=100.0, impact_score=72.5, source_consensus_score=25.0,
        has_conflicting_sources=False, entities=[{"type": "CRYPTO", "value": "BTCUSDT"}],
    )
    db_session.add(event)
    db_session.commit()
    event.cluster_id = event.id
    db_session.add(NewsImpact(
        news_event_id=event.id, asset_id=asset.id, impact="high", direction="bullish",
        confidence=0.8, horizon_hours=12, rationale="test", is_direct=True,
    ))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/news?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [e for e in resp.json() if e["headline"] == "Intelligence fields test"]
    assert len(matching) == 1
    body = matching[0]
    assert body["sentiment"] == "bullish"
    assert body["importance"] == "high"
    assert body["source_quality_score"] == 95.0
    assert body["impact_score"] == 72.5
    assert body["entities"] == [{"type": "CRYPTO", "value": "BTCUSDT"}]
    assert body["impacts"][0]["is_direct"] is True


def test_news_risk_requires_auth(client):
    resp = client.get("/api/news/risk")
    assert resp.status_code == 401


def test_news_risk_normal_with_no_events(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/news/risk", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == "normal"
    assert body["blocked"] is False
    assert body["size_multiplier"] == 1.0


def test_news_risk_critical_when_macro_event_imminent(client, db_session):
    db_session.add(MacroEvent(
        event="Fed Interest Rate Decision", country="US", currency="USD",
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        importance="critical", forecast=5.25, previous=5.25, status="scheduled",
    ))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/news/risk", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == "critical"
    assert body["blocked"] is True


def test_macro_calendar_requires_auth(client):
    resp = client.get("/api/macro")
    assert resp.status_code == 401


def test_macro_calendar_lists_upcoming_events(client, db_session):
    db_session.add(MacroEvent(
        event="CPI y/y", country="US", currency="USD",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
        importance="high", forecast=3.0, previous=2.9, status="scheduled",
    ))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/macro", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [e for e in resp.json() if e["event"] == "CPI y/y"]
    assert len(matching) == 1
    assert matching[0]["importance"] == "high"
    assert matching[0]["status"] == "scheduled"


def test_asset_news_context_requires_auth(client):
    resp = client.get("/api/news/context/BTCUSDT")
    assert resp.status_code == 401


def test_asset_news_context_unknown_symbol_404s(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/news/context/NOPE", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_asset_news_context_returns_recent_news(client, db_session):
    asset = Asset(symbol="NEWSCTX1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    event = NewsEvent(
        source="Reuters", published_at=datetime.now(timezone.utc), headline="Context test headline",
        category="crypto", sentiment="bullish", importance="medium",
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(
        news_event_id=event.id, asset_id=asset.id, impact="medium", direction="bullish",
        confidence=0.6, horizon_hours=12, rationale="test",
    ))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/news/context/NEWSCTX1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_symbol"] == "NEWSCTX1"
    assert any(n["headline"] == "Context test headline" for n in body["recent_news"])
    assert body["momentum"] is not None
    assert body["sentiment_shift"] is not None
