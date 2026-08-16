from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Asset, NewsEvent, NewsImpact, Pattern, PatternPerformance


def _login(client, db_session, email="newspatterns-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_list_news_requires_auth(client, db_session):
    resp = client.get("/api/news")
    assert resp.status_code == 401


def test_list_news_includes_impacts(client, db_session):
    asset = Asset(symbol="NEWSAPI1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    event = NewsEvent(source="Reuters", published_at=datetime.now(timezone.utc), headline="Headline for API test", category="crypto")
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(news_event_id=event.id, asset_id=asset.id, impact="high", direction="bullish", confidence=0.8, horizon_hours=12, rationale="test"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/news?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [e for e in resp.json() if e["headline"] == "Headline for API test"]
    assert len(matching) == 1
    assert matching[0]["impacts"][0]["asset_symbol"] == "NEWSAPI1"
    assert matching[0]["impacts"][0]["direction"] == "bullish"


def test_list_news_without_impacts_returns_empty_list(client, db_session):
    event = NewsEvent(source="Reuters", published_at=datetime.now(timezone.utc), headline="No impact headline", category="other")
    db_session.add(event)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/news?limit=50", headers={"Authorization": f"Bearer {token}"})
    matching = [e for e in resp.json() if e["headline"] == "No impact headline"]
    assert len(matching) == 1
    assert matching[0]["impacts"] == []


def test_list_patterns_requires_auth(client, db_session):
    resp = client.get("/api/patterns")
    assert resp.status_code == 401


def test_list_patterns_filters_by_asset(client, db_session):
    asset_a = Asset(symbol="PATAPI1", asset_class="crypto", is_active=True)
    asset_b = Asset(symbol="PATAPI2", asset_class="crypto", is_active=True)
    db_session.add_all([asset_a, asset_b])
    db_session.commit()

    db_session.add(Pattern(asset_id=asset_a.id, timeframe="1m", ts=datetime.now(timezone.utc), pattern_type="breakout", pattern_class="technical", direction="bullish", strength=0.8, meta={}))
    db_session.add(Pattern(asset_id=asset_b.id, timeframe="1m", ts=datetime.now(timezone.utc), pattern_type="momentum", pattern_class="technical", direction="bearish", strength=0.6, meta={}))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get(f"/api/patterns?asset_id={asset_a.id}&limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    symbols = {p["asset_symbol"] for p in resp.json()}
    assert symbols == {"PATAPI1"}


def test_pattern_performance_endpoint(client, db_session):
    db_session.add(PatternPerformance(pattern_type="breakout", regime="trending_bull", sample_size=10, win_rate=0.6, avg_r_multiple=1.2, expectancy=1.2))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/patterns/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [p for p in resp.json() if p["pattern_type"] == "breakout" and p["regime"] == "trending_bull"]
    assert len(matching) == 1
    assert matching[0]["sample_size"] == 10
    assert matching[0]["win_rate"] == 0.6
