def test_health_reports_database_and_market_data(client):
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    body = resp.json()
    names = {c["name"] for c in body["components"]}
    assert {"database", "market_data", "risk_engine", "news_feed"} <= names
    # ai_services is legitimately "yellow" without ANTHROPIC_API_KEY configured
    # (tests never set one) -- that's a valid state, not a failure, and must
    # not flip overall to "degraded" on its own (apps/api/routers/system.py).
    assert all(c["status"] in ("green", "yellow") for c in body["components"])
    assert body["overall"] == "green"


def test_root_reports_online(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"
