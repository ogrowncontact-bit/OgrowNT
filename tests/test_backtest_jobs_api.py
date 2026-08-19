from datetime import datetime, timedelta, timezone

from apps.api.security import hash_password
from packages.shared.models import OHLCV, AdminUser, Asset, BacktestJob, StrategyRow

TIMEFRAME = "1m"


def _login(client, db_session, email="lab-admin@example.com", password="correct-horse") -> str:
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


def _asset_with_uptrend(db_session, symbol: str):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    for i in range(200):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=200)


def test_create_job_requires_auth(client, db_session):
    resp = client.post("/api/backtests/jobs", json={"kind": "monte_carlo", "payload": {}})
    assert resp.status_code == 401


def test_create_job_rejects_unknown_kind(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/backtests/jobs", json={"kind": "not_a_real_kind", "payload": {}}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_create_and_poll_job_lifecycle(client, db_session):
    strategy = _strategy(db_session)
    asset, start, end = _asset_with_uptrend(db_session, "JOBAPILIFECYCLE")
    token = _login(client, db_session)

    payload = {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": end.isoformat(), "initial_capital": 10000.0,
    }
    resp = client.post(
        "/api/backtests/jobs", json={"kind": "backtest", "payload": payload},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    assert resp.json()["status"] == "queued"

    poll = client.get(f"/api/backtests/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert poll.status_code == 200
    assert poll.json()["status"] == "queued"

    listed = client.get("/api/backtests/jobs", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert any(j["id"] == job_id for j in listed.json())


def test_cancel_queued_job(client, db_session):
    strategy = _strategy(db_session)
    token = _login(client, db_session)
    resp = client.post(
        "/api/backtests/jobs", json={"kind": "sensitivity", "payload": {"strategy_id": strategy.id}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["id"]

    cancel = client.post(f"/api/backtests/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    cancel_again = client.post(f"/api/backtests/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancel_again.status_code == 409


def test_cancel_completed_job_conflicts(client, db_session):
    job = BacktestJob(kind="backtest", payload={}, status="completed")
    db_session.add(job)
    db_session.commit()
    token = _login(client, db_session)
    resp = client.post(f"/api/backtests/jobs/{job.id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


def test_get_unknown_job_404s(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/backtests/jobs/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_data_integrity_endpoint_reports_clean_data(client, db_session):
    asset, start, end = _asset_with_uptrend(db_session, "APIINTEGRITY")
    strategy = _strategy(db_session)
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/data-integrity",
        json={"strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME, "start_ts": start.isoformat(), "end_ts": end.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked"] is False
    assert body["bars_checked"] == 200


def test_data_integrity_endpoint_blocks_bad_data(client, db_session):
    asset = Asset(symbol="APIINTEGRITYBAD", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session)
    start = datetime.now(timezone.utc) - timedelta(minutes=50)
    for i in range(50):
        db_session.add(OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=100.0, high=90.0, low=95.0, close=100.0, volume=500.0, data_quality="high"))
    db_session.commit()
    token = _login(client, db_session)

    resp = client.post(
        "/api/backtests/data-integrity",
        json={"strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME, "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=50)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["blocked"] is True
    assert resp.json()["status"] == "BACKTEST_BLOCKED"


def test_reality_gap_endpoint_unknown_strategy_returns_note(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/backtests/reality-gap/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == ["strategy not found"]


def test_failure_check_endpoint_ok_with_no_data(client, db_session):
    strategy = _strategy(db_session, "failure-check-strategy")
    token = _login(client, db_session)
    resp = client.get(f"/api/backtests/failure-check/{strategy.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["verdict"] in ("STRATEGY_OK", "STRATEGY_REJECTED", "STRATEGY_QUARANTINED")


def test_compare_endpoint_builds_a_lab_table(client, db_session):
    strategy_a = _strategy(db_session, "trend_following_v1")
    strategy_b = _strategy(db_session, "momentum_v1")
    asset_a, start_a, end_a = _asset_with_uptrend(db_session, "COMPAREA")
    asset_b, start_b, end_b = _asset_with_uptrend(db_session, "COMPAREB")
    token = _login(client, db_session)

    run_a = client.post(
        "/api/backtests", json={"strategy_id": strategy_a.id, "asset_id": asset_a.id, "timeframe": TIMEFRAME, "start_ts": start_a.isoformat(), "end_ts": end_a.isoformat(), "initial_capital": 10000.0},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    run_b = client.post(
        "/api/backtests", json={"strategy_id": strategy_b.id, "asset_id": asset_b.id, "timeframe": TIMEFRAME, "start_ts": start_b.isoformat(), "end_ts": end_b.isoformat(), "initial_capital": 10000.0},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    compare = client.post(
        "/api/backtests/compare", json={"backtest_run_ids": [run_a["id"], run_b["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert compare.status_code == 200
    rows = compare.json()
    assert len(rows) == 2
    assert {r["strategy_code"] for r in rows} == {"trend_following_v1", "momentum_v1"}
    for row in rows:
        assert row["quality_score"] is not None
        assert row["status"] is not None


def test_compare_endpoint_404s_on_missing_run(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/backtests/compare", json={"backtest_run_ids": [999999]}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
