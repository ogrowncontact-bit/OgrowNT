from datetime import datetime, timedelta, timezone

from packages.shared.models import SystemState


def test_health_reports_database_and_market_data(client):
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    body = resp.json()
    names = {c["name"] for c in body["components"]}
    assert {"database", "market_data", "risk_engine", "news_feed", "worker"} <= names
    # ai_services is legitimately "yellow" without ANTHROPIC_API_KEY configured
    # (tests never set one) -- that's a valid state, not a failure, and must
    # not flip overall to "degraded" on its own (apps/api/routers/system.py).
    non_worker = [c for c in body["components"] if c["name"] != "worker"]
    assert all(c["status"] in ("green", "yellow") for c in non_worker)


def test_health_worker_is_red_without_a_heartbeat(client, db_session):
    # A freshly migrated system (or an `api` deployment with no `worker`
    # process running at all) has genuinely never recorded a heartbeat --
    # reporting that honestly as red (and therefore "overall": "degraded")
    # is the correct behavior, not a bug to paper over.
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    body = resp.json()
    worker = next(c for c in body["components"] if c["name"] == "worker")
    assert worker["status"] == "red"
    assert body["overall"] == "degraded"


def test_health_worker_is_green_with_a_recent_heartbeat(client, db_session):
    db_session.add(SystemState(id=True, worker_last_heartbeat=datetime.now(timezone.utc)))
    db_session.commit()

    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    worker = next(c for c in resp.json()["components"] if c["name"] == "worker")
    assert worker["status"] == "green"


def test_health_worker_is_red_with_a_stale_heartbeat(client, db_session):
    db_session.add(SystemState(id=True, worker_last_heartbeat=datetime.now(timezone.utc) - timedelta(hours=1)))
    db_session.commit()

    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    worker = next(c for c in resp.json()["components"] if c["name"] == "worker")
    assert worker["status"] == "red"
    assert "last heartbeat" in worker["detail"]


def test_root_reports_online(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"
