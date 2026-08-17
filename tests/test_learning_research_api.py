from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import (
    AdminUser,
    Asset,
    LearnedRule,
    MarketMemory,
    Position,
    StrategyPerformance,
    StrategyRow,
    Trade,
    TradeJournal,
)


def _login(client, db_session, email="learning-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_strategy_performance_list_includes_health_score(client, db_session):
    strategy = StrategyRow(code="learnapi_v1", name="learnapi_v1", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, as_of=datetime.now(timezone.utc), window_trades=10, total_trades=10,
            win_rate=0.7, profit_factor=2.0, expectancy=1.1, health_score=78.5, best_regime="trending_bull",
        )
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/learning/strategy-performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [r for r in resp.json() if r["strategy_code"] == "learnapi_v1"]
    assert len(matching) == 1
    assert matching[0]["health_score"] == 78.5
    assert matching[0]["best_regime"] == "trending_bull"


def test_strategy_performance_requires_auth(client, db_session):
    resp = client.get("/api/learning/strategy-performance")
    assert resp.status_code == 401


def test_strategy_performance_list_handles_strategy_with_no_history(client, db_session):
    strategy = StrategyRow(code="learnapi_empty_v1", name="learnapi_empty_v1", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/learning/strategy-performance", headers={"Authorization": f"Bearer {token}"})
    matching = [r for r in resp.json() if r["strategy_code"] == "learnapi_empty_v1"]
    assert len(matching) == 1
    assert matching[0]["health_score"] is None
    assert matching[0]["total_trades"] == 0


def test_trade_journal_list_returns_recent_entries(client, db_session):
    asset = Asset(symbol="JOURNALAPI", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="journalapi_v1", name="journalapi_v1", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="closed", realized_pnl=-5.0, exit_reason="stop_hit")
    db_session.add(position)
    db_session.commit()

    trade = Trade(position_id=position.id, pnl=-5.0, r_multiple=-1.0, outcome="loss", closed_at=datetime.now(timezone.utc))
    db_session.add(trade)
    db_session.commit()

    db_session.add(TradeJournal(trade_id=trade.id, expected_outcome="win", actual_outcome="loss", hypothesis="Regime shifted.", root_cause="regime_shift"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/learning/trade-journal?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [r for r in resp.json() if r["asset_symbol"] == "JOURNALAPI"]
    assert len(matching) == 1
    assert matching[0]["hypothesis"] == "Regime shifted."
    assert matching[0]["root_cause"] == "regime_shift"


def test_market_memory_list_and_similar(client, db_session):
    asset = Asset(symbol="MEMAPI", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    db_session.add(MarketMemory(ts=datetime.now(timezone.utc), asset_id=asset.id, context={"regime": "trending_bull", "pattern_type": "momentum", "direction": "long"}, outcome="win"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/learning/memory?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    matching = [r for r in resp.json() if r["asset_symbol"] == "MEMAPI"]
    assert len(matching) == 1

    similar = client.get(
        "/api/learning/memory/similar?regime=trending_bull&pattern_type=momentum&direction=long",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert similar.status_code == 200
    assert any(r["asset_symbol"] == "MEMAPI" for r in similar.json())


def test_learned_rules_filters_by_status(client, db_session):
    db_session.add(LearnedRule(scope="pattern:breakout:ranging", condition={}, conclusion="candidate rule", confidence=0.5, sample_size=10, status="candidate"))
    db_session.add(LearnedRule(scope="strategy:foo_v1", condition={}, conclusion="validated rule", confidence=0.8, sample_size=25, status="validated"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/research/rules?status=validated", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    conclusions = {r["conclusion"] for r in resp.json()}
    assert "validated rule" in conclusions
    assert "candidate rule" not in conclusions


def test_restore_strategy_requires_auth(client, db_session):
    strategy = StrategyRow(code="restoreapi_noauth_v1", name="x", family="trend", version="1.0", lifecycle_stage="quarantine")
    db_session.add(strategy)
    db_session.commit()

    resp = client.post(f"/api/strategies/{strategy.id}/restore", json={})
    assert resp.status_code == 401


def test_restore_strategy_success(client, db_session):
    strategy = StrategyRow(code="restoreapi_v1", name="x", family="trend", version="1.0", lifecycle_stage="quarantine")
    db_session.add(strategy)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.post(f"/api/strategies/{strategy.id}/restore", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["lifecycle_stage"] == "paper"


def test_restore_strategy_rejects_non_quarantined(client, db_session):
    strategy = StrategyRow(code="restoreapi_notq_v1", name="x", family="trend", version="1.0", lifecycle_stage="paper")
    db_session.add(strategy)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.post(f"/api/strategies/{strategy.id}/restore", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
