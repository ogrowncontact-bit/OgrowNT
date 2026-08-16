from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import OHLCV, AdminUser, Asset


def _login(client, db_session, email="marketdata-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_list_assets_requires_auth(client, db_session):
    resp = client.get("/api/assets")
    assert resp.status_code == 401


def test_list_assets_returns_seeded_assets(client, db_session):
    db_session.add(Asset(symbol="MDASSET1", asset_class="crypto", is_active=True))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/assets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    symbols = {a["symbol"] for a in resp.json()}
    assert "MDASSET1" in symbols


def test_market_data_requires_auth(client, db_session):
    asset = Asset(symbol="MDCANDLE1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    resp = client.get(f"/api/market-data/{asset.id}")
    assert resp.status_code == 401

    resp_latest = client.get(f"/api/market-data/{asset.id}/latest")
    assert resp_latest.status_code == 401


def test_market_data_returns_candles(client, db_session):
    asset = Asset(symbol="MDCANDLE2", asset_class="crypto", is_active=True)
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
    resp = client.get(f"/api/market-data/{asset.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp_latest = client.get(f"/api/market-data/{asset.id}/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp_latest.status_code == 200
    assert resp_latest.json()["close"] == 100.5
