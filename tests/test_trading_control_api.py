"""apps/api/routers/trading_control.py — "PROMPT 8" §58-59, §64-66, §78."""
from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.order_manager import open_position
from packages.shared.models import OHLCV, Asset, ManualAction, Order, Position, Signal, StrategyRow, SystemState, TradingEvent


def _login(client, db_session, email="trading-control-admin@example.com", password="x", role="admin") -> str:
    from packages.shared.models import AdminUser

    db_session.add(AdminUser(email=email, hashed_password=hash_password(password), role=role))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def test_status_endpoint_reports_starting_before_any_heartbeat(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/trading/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "starting"
    assert resp.json()["trading_mode"] == "paper"


def test_pause_then_resume_round_trip(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/trading/pause", json={"reason": "operator break"}, headers=headers)
    assert resp.status_code == 200
    state = db_session.get(SystemState, True)
    assert state.trading_paused
    assert state.paused_reason == "operator break"
    assert db_session.query(ManualAction).filter(ManualAction.action == "pause").count() == 1
    assert db_session.query(TradingEvent).filter(TradingEvent.event_type == "trading_paused").count() == 1

    resp = client.post("/api/trading/resume", headers=headers)
    assert resp.status_code == 200
    db_session.refresh(state)
    assert not state.trading_paused
    assert state.paused_reason is None
    assert db_session.query(ManualAction).filter(ManualAction.action == "resume").count() == 1


def test_pause_requires_admin_role(client, db_session):
    token = _login(client, db_session, email="viewer1@example.com", role="viewer")
    resp = client.post("/api/trading/pause", json={"reason": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_close_position_endpoint(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    asset = _asset_with_price(db_session, "APICLOSE", 100.0)
    strategy = StrategyRow(code="api_close_strategy", name="API Close", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="approved",
    )
    db_session.add(signal)
    db_session.commit()
    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None

    resp = client.post(f"/api/trading/positions/{position.id}/close", json={"reason": "manual test"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"

    db_session.refresh(position)
    assert position.exit_reason == "manual_close"
    action = db_session.query(ManualAction).filter(ManualAction.action == "close_position").first()
    assert action is not None
    assert action.entity_id == position.id
    assert action.reason == "manual test"
    assert action.before["status"] == "open"
    assert action.after["status"] == "closed"


def test_close_position_404_for_unknown_position(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/trading/positions/999999/close", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_close_already_closed_position_400(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    asset = _asset_with_price(db_session, "APICLOSEDUP", 100.0)
    strategy = StrategyRow(code="api_closedup_strategy", name="Closed", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, size=1.0, status="closed", exit_reason="stop_hit",
    )
    db_session.add(position)
    db_session.commit()

    resp = client.post(f"/api/trading/positions/{position.id}/close", json={}, headers=headers)
    assert resp.status_code == 400


def test_cancel_order_400_when_already_filled(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    order = Order(order_type="market", side="buy", qty=1.0, status="filled")
    db_session.add(order)
    db_session.commit()

    resp = client.post(f"/api/trading/orders/{order.id}/cancel", json={}, headers=headers)
    assert resp.status_code == 400


def test_reset_paper_account_requires_confirm(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/trading/reset-paper", json={"confirm": False}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_reset_paper_account_blocked_while_positions_open(client, db_session):
    token = _login(client, db_session)
    asset = _asset_with_price(db_session, "APIRESETBLOCK", 100.0)
    strategy = StrategyRow(code="api_reset_block_strategy", name="Reset Block", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(
        Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="open")
    )
    db_session.commit()

    resp = client.post("/api/trading/reset-paper", json={"confirm": True}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


def test_reset_paper_account_succeeds_and_resets_equity(client, db_session):
    from packages.portfolio.state import refresh_snapshot
    from packages.shared.settings import get_settings

    refresh_snapshot(db_session, cash=50_000.0)  # simulate a grown account
    token = _login(client, db_session)

    resp = client.post("/api/trading/reset-paper", json={"confirm": True}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    state = db_session.get(SystemState, True)
    assert state.last_reset_at is not None
    action = db_session.query(ManualAction).filter(ManualAction.action == "reset_paper_account").first()
    assert action is not None
    assert action.before["equity"] == 50_000.0
    assert action.after["equity"] == get_settings().initial_paper_capital

    portfolio_resp = client.get("/api/portfolio", headers={"Authorization": f"Bearer {token}"})
    assert portfolio_resp.json()["equity"] == get_settings().initial_paper_capital
    assert portfolio_resp.json()["drawdown_pct"] == 0.0  # not measured against the pre-reset 50k peak


def test_activity_feed_reflects_manual_actions(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/trading/pause", json={"reason": "test"}, headers=headers)

    resp = client.get("/api/trading/activity", headers=headers)
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()]
    assert "trading_paused" in event_types


def test_manual_actions_endpoint_lists_actions(client, db_session):
    token = _login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/trading/pause", json={"reason": "test"}, headers=headers)

    resp = client.get("/api/trading/manual-actions", headers=headers)
    assert resp.status_code == 200
    assert any(a["action"] == "pause" for a in resp.json())


def test_performance_endpoint_reports_zero_trades_today_when_none_exist(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/trading/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["trades_today"] == 0
    assert resp.json()["win_rate_today"] is None
