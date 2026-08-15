from datetime import datetime, timezone

from packages.shared.models import Asset, MarketRegime, OpportunityScore, Signal, StrategyRow


def _seed_opportunity(db_session, *, symbol="APITEST", tier="high_quality", score=85.0):
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
        signal_id=signal.id, technical=90, pattern=50, regime_fit=100, historical_edge=50,
        liquidity=80, news=50, risk_reward=70, strategy_performance=50,
        volatility_penalty=0, correlation_penalty=0, execution_cost_penalty=0, drawdown_penalty=0,
        final_score=score, tier=tier, notes={},
    )
    db_session.add(opp_score)
    db_session.commit()
    return asset, strategy, signal


def test_list_strategies(client, db_session):
    _seed_opportunity(db_session, symbol="STRATLIST")
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()}
    assert "strategy_stratlist" in codes


def test_strategy_performance_is_honestly_empty(client, db_session):
    _, strategy, _ = _seed_opportunity(db_session, symbol="PERF")
    resp = client.get(f"/api/strategies/{strategy.id}/performance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_trades"] == 0
    assert body["win_rate"] is None
    assert "Execution Engine" in body["note"]


def test_strategy_performance_404_for_unknown(client):
    resp = client.get("/api/strategies/999999/performance")
    assert resp.status_code == 404


def test_opportunities_excludes_ignore_tier(client, db_session):
    _seed_opportunity(db_session, symbol="GOODOPP", tier="high_quality", score=85.0)
    _seed_opportunity(db_session, symbol="BADOPP", tier="ignore", score=40.0)

    resp = client.get("/api/opportunities?limit=100")
    assert resp.status_code == 200
    symbols = {o["asset_symbol"] for o in resp.json()}
    assert "GOODOPP" in symbols
    assert "BADOPP" not in symbols


def test_signals_includes_ignore_tier(client, db_session):
    _seed_opportunity(db_session, symbol="AUDITME", tier="ignore", score=30.0)
    resp = client.get("/api/signals?limit=200")
    assert resp.status_code == 200
    symbols = {o["asset_symbol"] for o in resp.json()}
    assert "AUDITME" in symbols


def test_opportunity_detail_has_full_score_breakdown(client, db_session):
    _, _, signal = _seed_opportunity(db_session, symbol="DETAIL", tier="high_quality", score=85.0)
    resp = client.get(f"/api/opportunities/{signal.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_symbol"] == "DETAIL"
    assert body["score"]["final_score"] == 85.0
    assert body["score"]["regime_fit"] == 100.0


def test_opportunity_detail_404_for_unknown_signal(client):
    resp = client.get("/api/opportunities/999999")
    assert resp.status_code == 404


def test_regime_endpoint_returns_latest_per_asset(client, db_session):
    _seed_opportunity(db_session, symbol="REGIMETEST")
    resp = client.get("/api/regime")
    assert resp.status_code == 200
    entries = [r for r in resp.json() if r["asset_symbol"] == "REGIMETEST"]
    assert len(entries) == 1
    assert entries[0]["regime"] == "trending_bull"
