from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Asset, MarketRegime, OpportunityScore, Signal, StrategyRow


def _login(client, db_session, email="opportunities-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _seed_opportunity(
    db_session, *, symbol="APITEST", tier="high_quality", score=85.0, confidence=75.0,
    technical=90, pattern=50, regime_fit=100, historical_edge=50, liquidity=80, news=50,
    risk_reward=70, volatility_penalty=0, notes=None,
):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    strategy = StrategyRow(code=f"strategy_{symbol.lower()}", name="Test Strategy", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    regime = MarketRegime(
        asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc),
        regime="trending_bull", confidence=0.9, features={},
    )
    db_session.add(regime)
    db_session.commit()

    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc),
        direction="long", entry_price=100.0, stop_price=95.0, target_price=115.0,
        regime_id=regime.id, status="scored",
    )
    db_session.add(signal)
    db_session.commit()

    opp_score = OpportunityScore(
        signal_id=signal.id, technical=technical, pattern=pattern, regime_fit=regime_fit,
        historical_edge=historical_edge, liquidity=liquidity, news=news, risk_reward=risk_reward,
        strategy_performance=50, volatility_penalty=volatility_penalty, correlation_penalty=0,
        execution_cost_penalty=0, drawdown_penalty=0, final_score=score, confidence=confidence,
        tier=tier, notes=notes or {},
    )
    db_session.add(opp_score)
    db_session.commit()
    return asset, strategy, signal


def test_list_strategies_requires_auth(client, db_session):
    resp = client.get("/api/strategies")
    assert resp.status_code == 401


def test_list_strategies(client, db_session):
    _seed_opportunity(db_session, symbol="STRATLIST")
    token = _login(client, db_session)
    resp = client.get("/api/strategies", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()}
    assert "strategy_stratlist" in codes


def test_strategy_performance_is_honestly_empty(client, db_session):
    _, strategy, _ = _seed_opportunity(db_session, symbol="PERF")
    token = _login(client, db_session)
    resp = client.get(f"/api/strategies/{strategy.id}/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_trades"] == 0
    assert body["win_rate"] is None
    assert "No trades closed yet" in body["note"]


def test_strategy_performance_404_for_unknown(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/strategies/999999/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_opportunities_excludes_ignore_tier(client, db_session):
    _seed_opportunity(db_session, symbol="GOODOPP", tier="high_quality", score=85.0)
    _seed_opportunity(db_session, symbol="BADOPP", tier="ignore", score=40.0)

    token = _login(client, db_session)
    resp = client.get("/api/opportunities?limit=100", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    symbols = {o["asset_symbol"] for o in resp.json()}
    assert "GOODOPP" in symbols
    assert "BADOPP" not in symbols


def test_signals_includes_ignore_tier(client, db_session):
    _seed_opportunity(db_session, symbol="AUDITME", tier="ignore", score=30.0)
    token = _login(client, db_session)
    resp = client.get("/api/signals?limit=200", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    symbols = {o["asset_symbol"] for o in resp.json()}
    assert "AUDITME" in symbols


def test_opportunity_detail_has_full_score_breakdown(client, db_session):
    _, _, signal = _seed_opportunity(db_session, symbol="DETAIL", tier="high_quality", score=85.0, confidence=72.5)
    token = _login(client, db_session)
    resp = client.get(f"/api/opportunities/{signal.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_symbol"] == "DETAIL"
    assert body["score"]["final_score"] == 85.0
    assert body["score"]["regime_fit"] == 100.0
    # Confidence is a distinct field from the score itself (Prompt 3 §17/§20).
    assert body["score"]["confidence"] == 72.5


def test_opportunity_list_includes_confidence_separate_from_score(client, db_session):
    _seed_opportunity(db_session, symbol="CONFLIST", tier="watch", score=68.0, confidence=55.0)
    token = _login(client, db_session)
    resp = client.get("/api/opportunities?limit=100", headers={"Authorization": f"Bearer {token}"})
    row = next(o for o in resp.json() if o["asset_symbol"] == "CONFLIST")
    assert row["final_score"] == 68.0
    assert row["confidence"] == 55.0


def test_opportunity_why_evidence_confirms_strong_components(client, db_session):
    # High technical/regime_fit/risk_reward, real pattern alignment, real
    # historical sample -- every component should read as confirming evidence.
    _, _, signal = _seed_opportunity(
        db_session, symbol="STRONGWHY", tier="high_quality", score=88.0, confidence=90.0,
        technical=90, regime_fit=95, risk_reward=90, liquidity=85, historical_edge=80,
        notes={
            "pattern": {"pattern_detected": True, "pattern_type": "breakout", "aligned": True, "strength": 0.8},
            "historical_edge": {"pattern_expectancy": 1.2, "strategy_expectancy": 0.8, "insufficient_history": False},
            "news": {"news_count": 0},
        },
    )
    token = _login(client, db_session)
    resp = client.get(f"/api/opportunities/{signal.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    evidence = resp.json()["evidence"]
    assert len(evidence) > 0
    assert all(item["kind"] == "confirm" for item in evidence)
    texts = " ".join(item["text"] for item in evidence)
    assert "Breakout" in texts
    assert "Regime compatible" in texts


def test_opportunity_why_evidence_warns_on_weak_components(client, db_session):
    _, _, signal = _seed_opportunity(
        db_session, symbol="WEAKWHY", tier="watch", score=52.0, confidence=40.0,
        technical=20, regime_fit=15, risk_reward=10, liquidity=80, historical_edge=50,
        volatility_penalty=5.0,
        notes={
            "pattern": {"pattern_detected": False},
            "historical_edge": {"pattern_expectancy": None, "strategy_expectancy": None, "insufficient_history": True},
            "news": {"news_count": 0},
        },
    )
    token = _login(client, db_session)
    resp = client.get(f"/api/opportunities/{signal.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    evidence = resp.json()["evidence"]
    warnings = [item for item in evidence if item["kind"] == "warning"]
    texts = " ".join(item["text"] for item in warnings)
    assert "No supporting pattern detected" in texts
    assert "INSUFFICIENT_HISTORY" in texts
    assert "Volatility elevated" in texts


def test_opportunity_detail_404_for_unknown_signal(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/opportunities/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_regime_endpoint_returns_latest_per_asset(client, db_session):
    _seed_opportunity(db_session, symbol="REGIMETEST")
    token = _login(client, db_session)
    resp = client.get("/api/regime", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    entries = [r for r in resp.json() if r["asset_symbol"] == "REGIMETEST"]
    assert len(entries) == 1
    assert entries[0]["regime"] == "trending_bull"
