from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import (
    AdminUser,
    Asset,
    MarketRegime,
    OpportunityScore,
    Order,
    Position,
    RiskCheck,
    RiskDecision,
    Signal,
    StrategyRow,
    Trade,
)


def _login(client, db_session, email="trading-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _seed_trade(db_session, symbol: str):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    strategy = StrategyRow(code=f"api_strategy_{symbol.lower()}", name="API Test", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    regime = MarketRegime(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), regime="trending_bull", confidence=0.9, features={})
    db_session.add(regime)
    db_session.commit()

    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, regime_id=regime.id, status="executed",
    )
    db_session.add(signal)
    db_session.commit()

    db_session.add(OpportunityScore(
        signal_id=signal.id, technical=90, pattern=50, regime_fit=100, historical_edge=50, liquidity=80,
        news=50, risk_reward=70, strategy_performance=50, final_score=85.0, tier="high_quality", notes={},
    ))
    db_session.add(RiskCheck(signal_id=signal.id, check_name="risk_reward", passed=True, detail={"risk_reward": 3.0}))
    db_session.add(
        RiskCheck(
            signal_id=signal.id, check_name="position_sizing", passed=True,
            detail={"quantity": 1.0, "binding_constraint": "risk_budget", "belt_multiplier": 1.0, "strategy_health_multiplier": 1.0},
        )
    )
    db_session.add(RiskDecision(signal_id=signal.id, approved=True, approved_size=1.0, reason="approved", safety_belt_level="normal"))
    db_session.commit()

    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long", entry_price=101.0,
        current_stop=95.0, target_price=115.0, size=1.0, status="closed", closed_at=datetime.now(timezone.utc),
        exit_price=110.0, realized_pnl=9.0, exit_reason="target_hit",
    )
    db_session.add(position)
    db_session.commit()

    order = Order(position_id=position.id, signal_id=signal.id, order_type="market", side="sell", qty=1.0, status="filled", filled_price=110.0, fees=0.05, slippage_bps=2.0, is_paper=True)
    db_session.add(order)
    db_session.commit()

    trade = Trade(position_id=position.id, closed_order_id=order.id, pnl=9.0, r_multiple=1.5, outcome="win", is_paper=True, closed_at=datetime.now(timezone.utc))
    db_session.add(trade)
    db_session.commit()
    return asset, strategy, signal, position, trade


def _seed_open_position(db_session, symbol: str):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    strategy = StrategyRow(code=f"api_open_{symbol.lower()}", name="API Open", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()
    return asset, position


def test_positions_endpoint_requires_auth(client, db_session):
    resp = client.get("/api/positions")
    assert resp.status_code == 401


def test_positions_endpoint_filters_by_status(client, db_session):
    _, open_position = _seed_open_position(db_session, "APIOPEN")
    _, _, _, closed_position, _ = _seed_trade(db_session, "APICLOSED")
    token = _login(client, db_session)

    open_resp = client.get("/api/positions?status_filter=open", headers={"Authorization": f"Bearer {token}"})
    assert open_resp.status_code == 200
    open_ids = {p["id"] for p in open_resp.json()}
    assert open_position.id in open_ids
    assert closed_position.id not in open_ids

    closed_resp = client.get("/api/positions?status_filter=closed", headers={"Authorization": f"Bearer {token}"})
    closed_ids = {p["id"] for p in closed_resp.json()}
    assert closed_position.id in closed_ids


def test_trades_endpoint_lists_closed_trades(client, db_session):
    _, _, _, _, trade = _seed_trade(db_session, "APITRADES")
    token = _login(client, db_session)
    resp = client.get("/api/trades?limit=200", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    trade_ids = {t["id"] for t in resp.json()}
    assert trade.id in trade_ids


def test_orders_endpoint_lists_orders(client, db_session):
    _seed_trade(db_session, "APIORDERS")
    token = _login(client, db_session)
    resp = client.get("/api/orders?limit=200", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_trade_why_returns_full_audit_trail(client, db_session):
    _, _, _, _, trade = _seed_trade(db_session, "APIWHY")
    token = _login(client, db_session)
    resp = client.get(f"/api/trades/{trade.id}/why", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["trade"]["id"] == trade.id
    assert body["opportunity"] is not None
    assert body["opportunity"]["score"]["final_score"] == 85.0
    assert body["risk_decision"] is not None
    assert body["risk_decision"]["approved"] is True
    assert body["risk_decision"]["decision"] == "approved"
    assert body["risk_decision"]["reasons"] == []
    assert body["risk_decision"]["risk_reward"] == 3.0
    assert body["risk_decision"]["risk_amount"] == 1.0 * abs(100.0 - 95.0)


def test_trade_why_404_for_unknown_trade(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/trades/999999/why", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_risk_state_requires_auth(client):
    resp = client.get("/api/risk")
    assert resp.status_code == 401


def test_risk_state_reports_limits_and_recent_decisions(client, db_session):
    from apps.api.security import create_access_token
    from packages.shared.models import AdminUser

    admin = db_session.query(AdminUser).first()
    if admin is None:
        from apps.api.security import hash_password
        admin = AdminUser(email="riskstate@example.com", hashed_password=hash_password("x"))
        db_session.add(admin)
        db_session.commit()
    token, _ = create_access_token(subject=admin.email)

    _seed_trade(db_session, "APIRISKSTATE")
    resp = client.get("/api/risk?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert "per_trade" in body["limits"]
    assert "safety_belt_multipliers" in body["limits"]
    assert isinstance(body["recent_decisions"], list)
    assert len(body["recent_decisions"]) > 0
    decision = body["recent_decisions"][0]
    assert decision["decision"] == "approved"
    assert decision["reasons"] == []


def test_risk_state_marks_reduced_and_blocked_decisions(client, db_session):
    from apps.api.security import create_access_token

    admin = db_session.query(AdminUser).first()
    if admin is None:
        admin = AdminUser(email="riskreduced@example.com", hashed_password=hash_password("x"))
        db_session.add(admin)
        db_session.commit()
    token, _ = create_access_token(subject=admin.email)

    asset = Asset(symbol="APIREDUCEDBLOCKED", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="api_reduced_blocked", name="API Reduced", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    reduced_signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="approved",
    )
    blocked_signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="risk_rejected",
    )
    db_session.add_all([reduced_signal, blocked_signal])
    db_session.commit()

    db_session.add(RiskCheck(signal_id=reduced_signal.id, check_name="risk_reward", passed=True, detail={"risk_reward": 2.0}))
    db_session.add(
        RiskCheck(
            signal_id=reduced_signal.id, check_name="position_sizing", passed=True,
            detail={"quantity": 0.5, "binding_constraint": "risk_budget", "belt_multiplier": 0.5, "strategy_health_multiplier": 1.0},
        )
    )
    db_session.add(RiskDecision(signal_id=reduced_signal.id, approved=True, approved_size=0.5, reason="approved", safety_belt_level="defensive"))

    db_session.add(RiskCheck(signal_id=blocked_signal.id, check_name="daily_loss_limit", passed=False, detail={"daily_loss_pct": 5.0}))
    db_session.add(RiskDecision(signal_id=blocked_signal.id, approved=False, approved_size=None, reason="daily_loss_limit", safety_belt_level="normal"))
    db_session.commit()

    resp = client.get("/api/risk?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_signal = {d["signal_id"]: d for d in resp.json()["recent_decisions"]}

    reduced = by_signal[reduced_signal.id]
    assert reduced["decision"] == "reduced"
    assert "safety_belt_size_reduction" in reduced["reasons"]
    assert reduced["risk_amount"] == 0.5 * abs(100.0 - 95.0)
    assert reduced["position_size"] == 0.5

    blocked = by_signal[blocked_signal.id]
    assert blocked["decision"] == "blocked"
    assert blocked["reasons"] == ["daily_loss_limit"]
    assert blocked["risk_amount"] is None
    assert blocked["position_size"] is None
