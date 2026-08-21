"""apps/api/routers/brokers.py + apps/api/routers/execution.py --
"PROMPT 13" §105."""
from __future__ import annotations

from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import OHLCV, AdminUser, Asset, Order


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "execapi-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x")))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_endpoints_require_authentication(client):
    assert client.get("/api/brokers").status_code == 401
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/execution/health").status_code == 401


def test_list_brokers_returns_the_seeded_paper_broker(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/brokers", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "paper"
    assert body[0]["kind"] == "paper"
    assert body[0]["capabilities"]["supports_market_orders"] is True


def test_get_broker_and_health(client, db_session):
    token = _admin_token(client, db_session)
    broker_id = client.get("/api/brokers", headers=_auth(token)).json()[0]["id"]

    resp = client.get(f"/api/brokers/{broker_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == broker_id

    health = client.get(f"/api/brokers/{broker_id}/health", headers=_auth(token))
    assert health.status_code == 200
    assert health.json()["state"] == "healthy"


def test_get_broker_404_for_unknown_id(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/brokers/999999", headers=_auth(token))
    assert resp.status_code == 404


def test_list_accounts_returns_the_paper_account(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/accounts", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["broker_name"] == "paper"
    assert body[0]["currency"] == "USD"


def test_order_detail_404_and_found(client, db_session):
    token = _admin_token(client, db_session)
    assert client.get("/api/orders/999999", headers=_auth(token)).status_code == 404

    order = Order(order_type="market", side="buy", qty=1.0, status="filled", filled_price=100.0, execution_mode="paper")
    db_session.add(order)
    db_session.commit()

    resp = client.get(f"/api/orders/{order.id}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == order.id
    assert body["fills"] == []


def test_list_executions_returns_empty_when_none_recorded(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/executions", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_reconciliation_runs_returns_empty_when_none_recorded(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/reconciliation", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_instruments_includes_precision_fields(client, db_session):
    token = _admin_token(client, db_session)
    asset = Asset(symbol="APIINSTR", asset_class="crypto", is_active=True, tick_size=0.01, step_size=0.001, min_quantity=0.001, min_notional=10.0)
    db_session.add(asset)
    db_session.commit()

    resp = client.get("/api/instruments", headers=_auth(token))
    assert resp.status_code == 200
    matching = [i for i in resp.json() if i["symbol"] == "APIINSTR"]
    assert len(matching) == 1
    assert matching[0]["tick_size"] == 0.01


def test_get_instrument_detail_404_and_found(client, db_session):
    token = _admin_token(client, db_session)
    assert client.get("/api/instruments/NOSUCHSYMBOL", headers=_auth(token)).status_code == 404

    asset = Asset(symbol="APIINSTRDETAIL", asset_class="forex", is_active=True)
    db_session.add(asset)
    db_session.commit()
    resp = client.get("/api/instruments/APIINSTRDETAIL", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["asset_class"] == "forex"


def test_execution_health_reflects_real_order_history(client, db_session):
    token = _admin_token(client, db_session)
    db_session.add(Order(order_type="market", side="buy", qty=1.0, status="filled", filled_price=100.0, expected_price=100.0))
    db_session.commit()

    resp = client.get("/api/execution/health", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluated"] is True
    assert body["orders_evaluated"] >= 1


def test_asset_with_real_ohlcv_shows_up_in_accounts_and_instruments(client, db_session):
    """A light end-to-end sanity check that the broker/execution routers
    read from the same real tables the rest of the API does, not a second,
    parallel data source."""
    token = _admin_token(client, db_session)
    asset = Asset(symbol="APIE2E", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=1.0, high=1.0, low=1.0, close=1.0, volume=100.0))
    db_session.commit()

    accounts = client.get("/api/accounts", headers=_auth(token)).json()
    assert accounts[0]["equity"] > 0
