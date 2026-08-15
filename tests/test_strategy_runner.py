from datetime import datetime, timedelta, timezone

from apps.worker.strategy_runner import run_strategy_cycle
from packages.quant.strategies import ALL_STRATEGIES
from packages.shared.models import OHLCV, Asset, MarketRegime, OpportunityScore, Signal, StrategyRow


def _seed_strategies(db_session):
    existing = {code for (code,) in db_session.query(StrategyRow.code).all()}
    for strategy in ALL_STRATEGIES:
        if strategy.code in existing:
            continue
        db_session.add(StrategyRow(code=strategy.code, name=strategy.name, family=strategy.family, version=strategy.version))
    db_session.commit()


def _seed_trending_ohlcv(db_session, asset: Asset, n=60, step=0.6):
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    price = 100.0
    for i in range(n):
        price += step
        db_session.add(
            OHLCV(
                asset_id=asset.id,
                timeframe="1m",
                ts=ts + timedelta(minutes=i),
                open=price - 0.1,
                high=price + 0.2,
                low=price - 0.2,
                close=price,
                volume=100.0,
                data_quality="high",
            )
        )
    db_session.commit()


def test_strategy_cycle_creates_signals_and_scores_for_trending_asset(db_session):
    # run_strategy_cycle scans every active asset in the DB, so these tests
    # assert on rows scoped to their own asset rather than on the aggregate
    # summary counts, which other tests' assets also contribute to.
    asset = Asset(symbol="RUNNER1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    _seed_strategies(db_session)
    _seed_trending_ohlcv(db_session, asset, step=0.6)

    summary = run_strategy_cycle(db_session)
    assert summary["signals_created"] >= 1

    signals = db_session.query(Signal).filter(Signal.asset_id == asset.id).all()
    assert len(signals) >= 1
    # Trend-aligned strategies must agree with the uptrend; mean reversion is
    # deliberately counter-trend (worst_regimes includes trending_bull) and
    # may fire "short" here — that's correct behavior, not a bug.
    trend_aligned = [s for s in signals if s.strategy.code != "mean_reversion_v1"]
    assert trend_aligned
    assert all(s.direction == "long" for s in trend_aligned)

    regimes = db_session.query(MarketRegime).filter(MarketRegime.asset_id == asset.id).all()
    assert len(regimes) == 1
    assert regimes[0].regime == "trending_bull"

    scores = db_session.query(OpportunityScore).join(Signal).filter(Signal.asset_id == asset.id).all()
    assert len(scores) == len(signals)
    assert all(0 <= s.final_score <= 100 for s in scores)


def test_strategy_cycle_skips_assets_with_insufficient_history(db_session):
    asset = Asset(symbol="RUNNER2", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    _seed_strategies(db_session)
    _seed_trending_ohlcv(db_session, asset, n=5)  # far below MIN_CANDLES_REQUIRED

    run_strategy_cycle(db_session)

    assert db_session.query(MarketRegime).filter(MarketRegime.asset_id == asset.id).count() == 0
    assert db_session.query(Signal).filter(Signal.asset_id == asset.id).count() == 0


def test_strategy_cycle_ignores_inactive_assets(db_session):
    asset = Asset(symbol="RUNNER3", asset_class="crypto", is_active=False)
    db_session.add(asset)
    db_session.commit()
    _seed_strategies(db_session)
    _seed_trending_ohlcv(db_session, asset, step=0.6)

    run_strategy_cycle(db_session)

    assert db_session.query(MarketRegime).filter(MarketRegime.asset_id == asset.id).count() == 0
    assert db_session.query(Signal).filter(Signal.asset_id == asset.id).count() == 0
