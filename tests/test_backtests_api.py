from datetime import datetime, timedelta, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Asset, BacktestRun, StrategyRow

TIMEFRAME = "1m"


def _login(client, db_session, email="backtest-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _strategy(db_session, code: str = "trend_following_v1") -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _asset_with_uptrend(db_session, symbol: str) -> tuple[Asset, datetime, datetime]:
    from packages.shared.models import OHLCV

    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    for i in range(200):
        close = 100.0 * (1.004 ** i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=200)


def test_create_backtest_requires_auth(client, db_session):
    strategy = _strategy(db_session)
    asset, start, end = _asset_with_uptrend(db_session, "BTAPINOAUTH")
    resp = client.post("/api/backtests", json={
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": end.isoformat(), "initial_capital": 10000.0,
    })
    assert resp.status_code == 401


def test_create_backtest_runs_and_persists(client, db_session):
    strategy = _strategy(db_session)
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIRUN")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests",
        json={"strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME, "start_ts": start.isoformat(), "end_ts": end.isoformat(), "initial_capital": 10000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy_code"] == strategy.code
    assert body["asset_symbol"] == "BTAPIRUN"
    assert body["kind"] == "backtest"
    assert "equity_curve" in body and len(body["equity_curve"]) > 0
    assert "trades" in body

    persisted = db_session.query(BacktestRun).filter(BacktestRun.id == body["id"]).first()
    assert persisted is not None


def test_list_and_get_backtest(client, db_session):
    strategy = _strategy(db_session, "momentum_v1")
    asset, start, end = _asset_with_uptrend(db_session, "BTAPILIST")
    token = _login(client, db_session)

    create_resp = client.post(
        "/api/backtests",
        json={"strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME, "start_ts": start.isoformat(), "end_ts": end.isoformat(), "initial_capital": 10000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/backtests?strategy_id={strategy.id}")
    assert list_resp.status_code == 200
    assert any(r["id"] == run_id for r in list_resp.json())
    assert "equity_curve" not in list_resp.json()[0]  # summary view stays lean

    detail_resp = client.get(f"/api/backtests/{run_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == run_id
    assert "equity_curve" in detail_resp.json()


def test_get_unknown_backtest_404s(client, db_session):
    resp = client.get("/api/backtests/999999")
    assert resp.status_code == 404


def test_walk_forward_endpoint_persists_windows(client, db_session):
    strategy = _strategy(db_session, "breakout_v1")
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIWF")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/walkforward",
        json={
            "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
            "start_ts": start.isoformat(), "end_ts": end.isoformat(),
            "window_days": 100 / (24 * 60), "initial_capital": 10000.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["windows"]) == 2
    assert body["windows"][0]["group_label"] == body["group_label"]
    assert body["windows"][0]["window_index"] == 0
    assert body["windows"][1]["window_index"] == 1


def test_backtest_unregistered_strategy_code_rejected(client, db_session):
    strategy = StrategyRow(code="not_a_real_backtest_strategy", name="x", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIUNREG")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests",
        json={"strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME, "start_ts": start.isoformat(), "end_ts": end.isoformat(), "initial_capital": 10000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_promotion_check_is_read_only_and_public(client, db_session):
    strategy = _strategy(db_session, "promo_check_v1")
    resp = client.get(f"/api/strategies/{strategy.id}/promotion-check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is False
    assert len(body["reasons"]) > 0


def test_promote_requires_auth(client, db_session):
    strategy = _strategy(db_session, "promo_noauth_v1")
    resp = client.post(f"/api/strategies/{strategy.id}/promote")
    assert resp.status_code == 401


def test_promote_rejects_when_not_eligible(client, db_session):
    strategy = _strategy(db_session, "promo_reject_v1")
    token = _login(client, db_session)
    resp = client.post(f"/api/strategies/{strategy.id}/promote", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
    assert "reason" not in resp.json()  # sanity: just checking it's a normal detail-shaped error
    assert "detail" in resp.json()


def test_optimize_requires_auth(client, db_session):
    strategy = _strategy(db_session)
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIOPTNOAUTH")
    resp = client.post("/api/backtests/optimize", json={
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": end.isoformat(),
        "window_days": 100 / (24 * 60), "initial_capital": 10000.0,
    })
    assert resp.status_code == 401


def test_optimize_endpoint_runs_grid_and_persists_windows(client, db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIOPT")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/optimize",
        json={
            "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
            "start_ts": start.isoformat(), "end_ts": end.isoformat(),
            "window_days": 100 / (24 * 60), "initial_capital": 10000.0,
            "multipliers": [0.8, 1.0, 1.2],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["candidates"]) == 3**3  # trend_following_v1 has 3 numeric params
    assert "reason" in body

    first = body["candidates"][0]
    assert first["group_label"].startswith("opt-")
    assert len(first["windows"]) > 0
    assert first["windows"][0]["group_label"] == first["group_label"]

    persisted = db_session.query(BacktestRun).filter(BacktestRun.group_label == first["group_label"]).all()
    assert len(persisted) == len(first["windows"])


def test_optimize_endpoint_respects_max_combinations(client, db_session):
    strategy = _strategy(db_session, "breakout_v1")
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIOPTBOUND")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/optimize",
        json={
            "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
            "start_ts": start.isoformat(), "end_ts": end.isoformat(),
            "window_days": 100 / (24 * 60), "initial_capital": 10000.0,
            "multipliers": [0.8, 1.0, 1.2], "max_combinations": 5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["candidates"]) == 5


def test_optimize_unregistered_strategy_code_rejected(client, db_session):
    strategy = StrategyRow(code="not_a_real_optimize_strategy", name="x", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    asset, start, end = _asset_with_uptrend(db_session, "BTAPIOPTUNREG")
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/optimize",
        json={
            "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
            "start_ts": start.isoformat(), "end_ts": end.isoformat(),
            "window_days": 100 / (24 * 60), "initial_capital": 10000.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
