"""apps/api/realtime.py -- "PROMPT 14" §70, §107, §130-132: the /ws/{channel}
gateway. Auth here (_authenticate()) deliberately bypasses FastAPI's DI --
it opens its own fresh packages.shared.db.SessionLocal() rather than reusing
the request-scoped `db` dependency (a native WebSocket handshake has no
per-request Depends() cycle the way a REST call does) -- which means the
AdminUser row these tests authenticate against must be a REAL, separately
committed row, invisible to tests/conftest.py's db_session fixture (a single
connection's SAVEPOINT that's rolled back, never committed). See that
fixture's own docstring for why the usual db_session fixture cannot be used
here.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.testclient import WebSocketDisconnect

from apps.api.security import hash_password
from packages.events.bus import Event
from packages.shared.db import SessionLocal
from packages.shared.models import AdminUser


@pytest.fixture()
def real_admin():
    db = SessionLocal()
    email = f"ws-admin-{uuid4().hex[:8]}@example.com"
    try:
        db.add(AdminUser(email=email, hashed_password=hash_password("x")))
        db.commit()
    finally:
        db.close()
    try:
        yield email
    finally:
        db = SessionLocal()
        try:
            db.query(AdminUser).filter(AdminUser.email == email).delete()
            db.commit()
        finally:
            db.close()


def _login(client, email: str, password: str = "x") -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_ws_rejects_a_connection_with_no_token(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/system"):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_a_connection_with_a_garbage_token(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/system?token=not-a-real-jwt"):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_a_token_for_an_admin_that_no_longer_exists(client):
    from apps.api.security import create_access_token

    token, _ = create_access_token("ghost-admin-does-not-exist@example.com")
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/system?token={token}"):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_an_unknown_channel_even_with_a_valid_token(client, real_admin):
    token = _login(client, real_admin)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/not-a-real-channel?token={token}"):
            pass
    assert exc_info.value.code == 4404


def test_ws_accepts_a_valid_token_and_a_real_channel(client, real_admin):
    token = _login(client, real_admin)
    with client.websocket_connect(f"/ws/system?token={token}") as ws:
        assert ws is not None


def test_ws_delivers_an_event_published_on_its_own_channel(client, real_admin):
    token = _login(client, real_admin)
    with client.websocket_connect(f"/ws/system?token={token}") as ws:
        event = Event(event_type="trading_paused", source="test", channel="system", payload={"reason": "test-pause"})
        # publish() touches asyncio.Queue internals -- must run on the same
        # event loop the WS handler's queue belongs to, not this (foreground)
        # thread, hence portal.call rather than a direct call.
        ws.portal.call(client.app.state.bus.publish, event)
        message = ws.receive_json()
    assert message["event_type"] == "trading_paused"
    assert message["channel"] == "system"
    assert message["payload"]["reason"] == "test-pause"


def test_ws_never_delivers_an_event_published_on_a_different_channel(client, real_admin):
    token = _login(client, real_admin)
    with client.websocket_connect(f"/ws/portfolio?token={token}") as ws:
        other_channel_event = Event(event_type="trading_paused", source="test", channel="system", payload={})
        this_channel_event = Event(event_type="position_opened", source="test", channel="portfolio", payload={"marker": "expected"})
        ws.portal.call(client.app.state.bus.publish, other_channel_event)
        ws.portal.call(client.app.state.bus.publish, this_channel_event)
        message = ws.receive_json()
    assert message["payload"].get("marker") == "expected"


def test_ws_unsubscribes_from_the_bus_on_disconnect(client, real_admin):
    token = _login(client, real_admin)
    before = client.app.state.bus.subscriber_count("alerts")
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        during = ws.portal.call(client.app.state.bus.subscriber_count, "alerts")
    after = client.app.state.bus.subscriber_count("alerts")
    assert before == 0
    assert during == 1
    assert after == 0
