"""Global Market Intelligence API -- "PROMPT 11" §91."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.api.security import hash_password
from packages.shared.models import (
    OHLCV,
    AdminUser,
    Anomaly,
    Asset,
    CorrelationMatrixEntry,
    MarketMemory,
    OpportunityCluster,
    VolatilityEvent,
    WatchlistEntry,
)

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def _login(client, db_session, email="global-market-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _asset(db_session, symbol: str, **overrides) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", **overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_universe_endpoint_requires_auth(client):
    resp = client.get("/api/global-market/universe")
    assert resp.status_code == 401


def test_universe_endpoint_lists_and_filters_assets(client, db_session):
    token = _login(client, db_session)
    _asset(db_session, "GMAPI_ACTIVE", status="active")
    _asset(db_session, "GMAPI_QUAR", status="quarantined")

    resp = client.get("/api/global-market/universe", headers=_headers(token))
    assert resp.status_code == 200
    symbols = {row["symbol"] for row in resp.json()}
    assert {"GMAPI_ACTIVE", "GMAPI_QUAR"} <= symbols

    filtered = client.get("/api/global-market/universe?status_filter=quarantined", headers=_headers(token))
    filtered_symbols = {row["symbol"] for row in filtered.json()}
    assert "GMAPI_QUAR" in filtered_symbols
    assert "GMAPI_ACTIVE" not in filtered_symbols


def test_volatility_endpoint_lists_and_filters_by_asset(client, db_session):
    token = _login(client, db_session)
    asset = _asset(db_session, "GMAPI_VOL")
    db_session.add(
        VolatilityEvent(
            asset_id=asset.id, ts=_START, timeframe="1m", event_type="spike", realized_vol=0.05, percentile=97.0,
            regime="extreme",
        )
    )
    db_session.commit()

    resp = client.get(f"/api/global-market/volatility?asset_id={asset.id}", headers=_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["regime"] == "extreme"


def test_anomalies_endpoint_lists_and_filters_by_reviewed(client, db_session):
    token = _login(client, db_session)
    asset = _asset(db_session, "GMAPI_ANOM")
    db_session.add(
        Anomaly(asset_id=asset.id, anomaly_type="price_move", score=80.0, evidence={"z_score": 3.0}, reviewed=False)
    )
    db_session.commit()

    resp = client.get("/api/global-market/anomalies?reviewed=false", headers=_headers(token))
    assert resp.status_code == 200
    assert any(row["asset_id"] == asset.id for row in resp.json())


def test_watchlist_endpoint_excludes_removed_by_default(client, db_session):
    token = _login(client, db_session)
    active_asset = _asset(db_session, "GMAPI_WL_ACTIVE")
    removed_asset = _asset(db_session, "GMAPI_WL_REMOVED")
    db_session.add(
        WatchlistEntry(asset_id=active_asset.id, reason="anomaly", status="active", added_at=_START, updated_at=_START)
    )
    db_session.add(
        WatchlistEntry(
            asset_id=removed_asset.id, reason="anomaly", status="removed", added_at=_START, updated_at=_START,
            removed_at=_START, removal_reason="manual",
        )
    )
    db_session.commit()

    resp = client.get("/api/global-market/watchlist", headers=_headers(token))
    ids = {row["asset_id"] for row in resp.json()}
    assert active_asset.id in ids
    assert removed_asset.id not in ids

    resp_all = client.get("/api/global-market/watchlist?include_removed=true", headers=_headers(token))
    ids_all = {row["asset_id"] for row in resp_all.json()}
    assert removed_asset.id in ids_all


def test_clusters_endpoint_lists_persisted_clusters(client, db_session):
    token = _login(client, db_session)
    db_session.add(
        OpportunityCluster(
            ts=_START, signal_ids=[1, 2], asset_ids=[10, 20], direction="long", factor="crypto_correlation",
            avg_correlation=0.9, combined_risk=0.9, ranking_penalty=0.2,
        )
    )
    db_session.commit()

    resp = client.get("/api/global-market/clusters", headers=_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["direction"] == "long"


def test_sessions_endpoint_returns_named_sessions_and_overlaps(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/global-market/sessions", headers=_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    session_names = {s["session"] for s in body["sessions"]}
    assert {"new_york", "london", "tokyo"} <= session_names
    assert isinstance(body["active_overlaps"], list)


def test_structure_endpoint_404_for_unknown_symbol(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/global-market/structure/NOT_A_REAL_SYMBOL", headers=_headers(token))
    assert resp.status_code == 404


def test_structure_endpoint_returns_a_reading_for_a_known_asset(client, db_session):
    token = _login(client, db_session)
    asset = _asset(db_session, "GMAPI_STRUCT")
    for i in range(10):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=100.0, high=100.5,
                low=99.5, close=100.0, volume=10.0, data_quality="high",
            )
        )
    db_session.commit()

    resp = client.get("/api/global-market/structure/GMAPI_STRUCT", headers=_headers(token))
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "GMAPI_STRUCT"
    assert "structure" in resp.json()


def test_pairs_endpoint_rejects_malformed_asset_ids(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/global-market/pairs?asset_ids=not-a-number", headers=_headers(token))
    assert resp.status_code == 400


def test_pairs_endpoint_finds_a_correlated_pair(client, db_session):
    token = _login(client, db_session)
    asset_a = _asset(db_session, "GMAPI_PAIR_A")
    asset_b = _asset(db_session, "GMAPI_PAIR_B")
    closes_b = [100.0 + i * 0.1 for i in range(150)]
    closes_a = [2.0 * v for v in closes_b]
    closes_a[-1] += 500.0
    for asset, closes in ((asset_a, closes_a), (asset_b, closes_b)):
        for i, close in enumerate(closes):
            db_session.add(
                OHLCV(
                    asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.1,
                    low=close - 0.1, close=close, volume=10.0, data_quality="high",
                )
            )
    db_session.add(
        CorrelationMatrixEntry(ts=_START, asset_id_a=asset_a.id, asset_id_b=asset_b.id, window_days=30, correlation=0.95)
    )
    db_session.commit()

    resp = client.get(f"/api/global-market/pairs?asset_ids={asset_a.id},{asset_b.id}", headers=_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "not an execution signal" in body[0]["disclaimer"]


def test_historical_analog_endpoint_returns_honest_shape_with_no_history(client, db_session):
    token = _login(client, db_session)
    resp = client.get(
        "/api/global-market/historical-analog?regime=trending_bull&pattern_type=breakout&direction=long",
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_size"] == 0
    assert body["quality"] == "low_sample"


def test_historical_analog_endpoint_reflects_seeded_memory(client, db_session):
    token = _login(client, db_session)
    db_session.add(
        MarketMemory(
            ts=_START, context={"regime": "panic", "pattern_type": "reversal", "direction": "short"}, outcome="win",
            signal_id=None,
        )
    )
    db_session.commit()

    resp = client.get(
        "/api/global-market/historical-analog?regime=panic&pattern_type=reversal&direction=short",
        headers=_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["sample_size"] == 1


def test_opportunities_response_includes_prompt11_fields(client, db_session):
    from packages.shared.models import MarketRegime, OpportunityScore, Signal, StrategyRow

    token = _login(client, db_session)
    asset = _asset(db_session, "GMAPI_OPP")
    strategy = StrategyRow(code="gmapi_strategy", name="gmapi_strategy", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    regime = MarketRegime(asset_id=asset.id, timeframe="1m", ts=_START, regime="trending_bull", confidence=0.9, features={})
    db_session.add(regime)
    db_session.commit()
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, regime_id=regime.id, ts=_START, direction="long",
        entry_price=100.0, stop_price=95.0, status="scored", opportunity_type="breakout",
        fingerprint="abc123", expires_at=_START + timedelta(hours=4),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.add(
        OpportunityScore(
            signal_id=signal.id, technical=90, pattern=50, regime_fit=100, historical_edge=50, liquidity=80,
            news=50, risk_reward=70, strategy_performance=50, final_score=85.0, tier="high_quality", confidence=75.0,
        )
    )
    db_session.commit()

    resp = client.get("/api/opportunities", headers=_headers(token))
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["signal_id"] == signal.id)
    assert row["opportunity_type"] == "breakout"
    assert row["fingerprint"] == "abc123"
    assert row["expires_at"] is not None
