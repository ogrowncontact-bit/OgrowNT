from datetime import datetime, timedelta, timezone

from apps.api.security import hash_password
from packages.shared.models import OHLCV, AdminUser, Asset, MarketEvent


def _login(client, db_session, email="market-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_market_endpoints_require_auth(client, db_session):
    assert client.get("/api/market/overview").status_code == 401
    assert client.get("/api/market/assets").status_code == 401
    assert client.get("/api/market/events").status_code == 401
    assert client.get("/api/market/data-quality").status_code == 401
    assert client.get("/api/market/BTCUSDT").status_code == 401
    assert client.get("/api/market/BTCUSDT/ohlcv").status_code == 401


def test_market_overview_reports_data_source_and_active_assets(client, db_session):
    active = Asset(symbol="MKTOV1", asset_class="crypto", is_active=True)
    inactive = Asset(symbol="MKTOV2", asset_class="crypto", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/overview", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()

    assert body["data_source"]["provider"] == "mock"
    assert body["data_source"]["is_live"] is False

    symbols = {a["symbol"] for a in body["assets"]}
    assert "MKTOV1" in symbols
    assert "MKTOV2" not in symbols  # inactive assets excluded


def test_market_overview_asset_without_history_reports_honest_nulls(client, db_session):
    asset = Asset(symbol="MKTNODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/overview", headers=_auth(token))
    row = next(a for a in resp.json()["assets"] if a["symbol"] == "MKTNODATA")

    assert row["price"] is None
    assert row["last_update"] is None
    assert row["data_quality_status"] == "DATA_UNSAFE"


def test_market_asset_detail_returns_latest_price(client, db_session):
    asset = Asset(symbol="MKTDETAIL", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(
            asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0, data_quality="high",
        )
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/MKTDETAIL", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["price"] == 100.5


def test_market_asset_detail_404_for_unknown_symbol(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/market/DOESNOTEXIST", headers=_auth(token))
    assert resp.status_code == 404


def test_market_ohlcv_returns_candles_by_symbol(client, db_session):
    asset = Asset(symbol="MKTOHLCV", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(
            asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0, data_quality="high",
        )
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/MKTOHLCV/ohlcv", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["close"] == 100.5


def test_market_events_filters_by_symbol_and_severity(client, db_session):
    asset_a = Asset(symbol="MKTEVA", asset_class="crypto", is_active=True)
    asset_b = Asset(symbol="MKTEVB", asset_class="crypto", is_active=True)
    db_session.add_all([asset_a, asset_b])
    db_session.commit()
    db_session.add_all(
        [
            MarketEvent(
                asset_id=asset_a.id, event_type="VOLUME_SPIKE", timeframe="1m", severity="HIGH",
                price=100.0, volume=1000.0, confidence=0.9, meta={},
            ),
            MarketEvent(
                asset_id=asset_b.id, event_type="PRICE_MOVEMENT", timeframe="1m", severity="LOW",
                price=50.0, volume=10.0, confidence=0.3, meta={},
            ),
        ]
    )
    db_session.commit()

    token = _login(client, db_session)
    resp_all = client.get("/api/market/events", headers=_auth(token))
    assert resp_all.status_code == 200
    types = {e["event_type"] for e in resp_all.json()}
    assert {"VOLUME_SPIKE", "PRICE_MOVEMENT"} <= types

    resp_symbol = client.get("/api/market/events?symbol=MKTEVA", headers=_auth(token))
    assert all(e["asset_symbol"] == "MKTEVA" for e in resp_symbol.json())
    assert len(resp_symbol.json()) == 1

    resp_severity = client.get("/api/market/events?severity=HIGH", headers=_auth(token))
    assert all(e["severity"] == "HIGH" for e in resp_severity.json())


def test_market_events_pagination(client, db_session):
    asset = Asset(symbol="MKTEVPAGE", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    base_ts = datetime.now(timezone.utc)
    db_session.add_all(
        [
            MarketEvent(
                asset_id=asset.id, event_type="ANOMALY", timeframe="1m", severity="LOW",
                price=100.0, volume=1.0, confidence=0.1, meta={}, ts=base_ts - timedelta(minutes=i),
            )
            for i in range(5)
        ]
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/events?symbol=MKTEVPAGE&limit=2&offset=0", headers=_auth(token))
    assert len(resp.json()) == 2
    resp2 = client.get("/api/market/events?symbol=MKTEVPAGE&limit=2&offset=2", headers=_auth(token))
    assert len(resp2.json()) == 2
    assert resp.json()[0]["id"] != resp2.json()[0]["id"]


def test_market_data_quality_lists_active_assets(client, db_session):
    asset = Asset(symbol="MKTDQ", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/market/data-quality", headers=_auth(token))
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["symbol"] == "MKTDQ")
    assert row["status"] == "DATA_UNSAFE"  # no OHLCV rows yet
    assert 0 <= row["quality_score"] <= 100
