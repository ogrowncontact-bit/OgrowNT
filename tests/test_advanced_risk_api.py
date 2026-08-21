"""apps/api/routers/risk.py's "PROMPT 12" additions: /api/risk/advanced,
/breakers, /concentration, /stress, /kill-switch/*, /config-versions*."""
from __future__ import annotations

import pytest

from apps.api.security import hash_password
from packages.risk import circuit_breakers as cb
from packages.risk.config import CONFIG_PATH
from packages.shared.models import AdminUser, SystemState


@pytest.fixture()
def restore_risk_limits_file():
    """The PATCH /api/system/risk-limits endpoint writes the real
    config/risk_limits.yaml on disk (not something the db_session
    transaction rollback undoes) -- guarantee it's restored byte-for-byte
    even if a test assertion fails mid-way."""
    original = CONFIG_PATH.read_text()
    yield
    CONFIG_PATH.write_text(original)


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "advrisk-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x")))
    db_session.commit()
    return _login(client, email, "x")


def _viewer_token(client, db_session, email: str = "advrisk-viewer@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x"), role="viewer"))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _healthy_system_state(db_session) -> None:
    import datetime as dt

    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = True
    state.trading_paused = False
    state.safety_belt_level = "normal"
    state.worker_last_heartbeat = dt.datetime.now(dt.timezone.utc)
    db_session.add(state)
    db_session.commit()


def test_advanced_risk_requires_auth(client):
    resp = client.get("/api/risk/advanced")
    assert resp.status_code == 401


def test_advanced_risk_returns_normal_state(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/advanced", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_state"] == "normal"
    assert body["capital_preservation_mode"] is False
    assert body["zero_trade_mode"] is False
    assert "reasons" in body


def test_breakers_returns_four_portfolio_wide_by_default(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/breakers", headers=_auth(token))
    assert resp.status_code == 200
    names = {b["name"] for b in resp.json()}
    assert names == {"system", "portfolio", "execution", "data"}


def test_breakers_includes_strategy_and_asset_when_given(client, db_session):
    from packages.shared.models import Asset, StrategyRow

    strategy = StrategyRow(code="advrisk_breaker_strategy", name="x", family="test", version="1.0")
    asset = Asset(symbol="ADVRISK_BREAKER", asset_class="crypto")
    db_session.add_all([strategy, asset])
    db_session.commit()
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)

    resp = client.get(f"/api/risk/breakers?strategy_id={strategy.id}&asset_id={asset.id}", headers=_auth(token))
    assert resp.status_code == 200
    names = {b["name"] for b in resp.json()}
    assert names == {"system", "portfolio", "execution", "data", "strategy", "asset"}


def test_concentration_endpoint_with_no_positions(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/concentration", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_position_count"] == 0
    assert body["concentration_state"] == "low"


def test_stress_endpoint_reports_insufficient_history(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/stress?num_simulations=50", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient_history"] is False
    assert body["var_pct"] is None
    assert body["var_note"] is not None


def test_kill_switch_state_endpoint_defaults_to_armed(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/kill-switch/state", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["kill_switch_state"] == "armed"


def test_viewer_cannot_start_kill_switch_recovery(client, db_session):
    _healthy_system_state(db_session)
    token = _viewer_token(client, db_session)
    resp = client.post("/api/risk/kill-switch/recovery/start", headers=_auth(token))
    assert resp.status_code == 403


def test_start_recovery_requires_locked_state(client, db_session):
    _healthy_system_state(db_session)  # ARMED, never triggered
    token = _admin_token(client, db_session)
    resp = client.post("/api/risk/kill-switch/recovery/start", headers=_auth(token))
    assert resp.status_code == 400


def test_full_kill_switch_recovery_flow_via_api(client, db_session):
    import datetime as dt

    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.worker_last_heartbeat = dt.datetime.now(dt.timezone.utc)
    db_session.add(state)
    db_session.commit()
    cb.trigger_kill_switch(db_session, reason="test trip", actor="system")

    token = _admin_token(client, db_session)

    started = client.post("/api/risk/kill-switch/recovery/start", headers=_auth(token))
    assert started.status_code == 200
    assert started.json()["kill_switch_state"] == "recovery"
    assert started.json()["trading_enabled"] is False

    readiness = client.get("/api/risk/kill-switch/recovery/readiness", headers=_auth(token))
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True

    confirmed = client.post("/api/risk/kill-switch/recovery/confirm", headers=_auth(token))
    assert confirmed.status_code == 200
    assert confirmed.json()["kill_switch_state"] == "armed"
    assert confirmed.json()["trading_enabled"] is True


def test_config_versions_empty_before_any_patch(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/config-versions", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_patch_risk_limits_records_a_config_version(client, db_session, restore_risk_limits_file):
    token = _admin_token(client, db_session)
    resp = client.patch(
        "/api/system/risk-limits", json={"per_trade": {"max_risk_pct": 0.75}}, headers=_auth(token),
    )
    assert resp.status_code == 200

    versions = client.get("/api/risk/config-versions", headers=_auth(token))
    assert versions.status_code == 200
    body = versions.json()
    assert len(body) >= 1
    latest = body[0]
    assert latest["status"] == "active"
    assert latest["parameters"]["per_trade"]["max_risk_pct"] == 0.75


def test_config_version_diff_endpoint(client, db_session, restore_risk_limits_file):
    token = _admin_token(client, db_session)
    client.patch("/api/system/risk-limits", json={"per_trade": {"max_risk_pct": 0.5}}, headers=_auth(token))
    r2 = client.patch("/api/system/risk-limits", json={"per_trade": {"max_risk_pct": 0.6}}, headers=_auth(token))
    assert r2.status_code == 200

    versions = client.get("/api/risk/config-versions", headers=_auth(token)).json()
    v2_number = versions[0]["version"]
    v1_number = versions[1]["version"]

    diff = client.get(f"/api/risk/config-versions/diff/{v1_number}/{v2_number}", headers=_auth(token))
    assert diff.status_code == 200
    diffs = diff.json()
    assert any(d["key"] == "per_trade.max_risk_pct" for d in diffs)


def test_config_version_missing_returns_404(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/risk/config-versions/999999", headers=_auth(token))
    assert resp.status_code == 404
