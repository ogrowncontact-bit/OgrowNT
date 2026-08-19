""""PROMPT 7": configurable execution models, latency, enriched metrics,
data-integrity gating, look-ahead protection, and news-aware data leakage
protection -- all exercised against packages/backtest/engine.py directly.
"""
from datetime import datetime, timedelta, timezone

from packages.backtest.engine import run_backtest
from packages.backtest.execution_models import (
    ExecutionConfig,
    FeeModel,
    LatencyModel,
    SlippageModel,
    default_fee_model,
    default_slippage_model,
    simulate_fill_configurable,
)
from packages.execution.fills import simulate_fill
from packages.quant.strategies import TrendFollowingStrategy
from packages.shared.models import OHLCV, Asset, NewsEvent, NewsImpact

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 200) -> datetime:
    for i in range(bars):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i),
                open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high",
            )
        )
    db_session.commit()
    return start + timedelta(minutes=bars)


def test_default_execution_config_matches_legacy_simulate_fill():
    fee_model, slippage_model = default_fee_model(), default_slippage_model()
    fill = simulate_fill_configurable(mid_price=100.0, volume=500.0, qty=10.0, side="buy", fee_model=fee_model, slippage_model=slippage_model)
    legacy = simulate_fill(mid_price=100.0, volume=500.0, qty=10.0, side="buy")
    assert fill.price == legacy.price
    assert fill.fees == legacy.fees
    assert abs(fill.slippage_bps - legacy.slippage_bps) < 0.01


def test_fee_model_kinds_compute_expected_amounts():
    percentage = FeeModel(kind="percentage", rate=0.001)
    assert percentage.compute(price=100.0, qty=10.0) == 1.0

    fixed = FeeModel(kind="fixed", fixed_amount=2.5)
    assert fixed.compute(price=100.0, qty=10.0) == 2.5

    tiered = FeeModel(kind="tiered", rate=0.002, tiers=((0.0, 0.002), (5000.0, 0.0005)))
    assert tiered.compute(price=100.0, qty=10.0) == round(1000 * 0.002, 4)  # below the 5000 tier
    assert tiered.compute(price=100.0, qty=100.0) == round(10000 * 0.0005, 4)  # above the 5000 tier

    provider = FeeModel(kind="provider_specific", provider="crypto_spot_maker")
    assert provider.compute(price=100.0, qty=10.0) == round(1000 * 0.0004, 4)


def test_slippage_model_kinds_scale_as_expected():
    fixed = SlippageModel(kind="fixed", fixed_amount=0.5)
    assert fixed.price_offset(mid_price=100.0, qty=10.0, volume=500.0) == 0.5

    liquidity = SlippageModel(kind="liquidity_based", slippage_bps=2.0)
    thin = liquidity.price_offset(mid_price=100.0, qty=400.0, volume=500.0)
    thick = liquidity.price_offset(mid_price=100.0, qty=1.0, volume=500.0)
    assert thin > thick  # a bigger order relative to volume costs more

    volatility = SlippageModel(kind="volatility_based", slippage_bps=2.0)
    calm = volatility.price_offset(mid_price=100.0, qty=10.0, volume=500.0, atr_pct=0.01)
    stormy = volatility.price_offset(mid_price=100.0, qty=10.0, volume=500.0, atr_pct=0.05)
    assert stormy > calm


def test_higher_fees_reduce_net_return(db_session):
    asset = _asset(db_session, "V2FEES")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    end = _insert_uptrend(db_session, asset, start)

    cheap = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
        execution=ExecutionConfig(fee_model=FeeModel(kind="percentage", rate=0.0001)),
    )
    expensive = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
        execution=ExecutionConfig(fee_model=FeeModel(kind="percentage", rate=0.02)),
    )
    assert cheap.num_trades > 0 and expensive.num_trades > 0
    assert expensive.net_return < cheap.net_return


def test_latency_delays_entry_and_produces_a_different_fill(db_session):
    asset = _asset(db_session, "V2LATENCY")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    end = _insert_uptrend(db_session, asset, start)

    immediate = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
    )
    delayed = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
        execution=ExecutionConfig(latency=LatencyModel(bars=3)),
    )
    assert immediate.num_trades > 0 and delayed.num_trades > 0
    # On a monotonic uptrend, entering 3 bars later means a strictly higher entry price for every trade.
    for immediate_trade, delayed_trade in zip(immediate.trades, delayed.trades, strict=False):
        assert delayed_trade["entry_price"] > immediate_trade["entry_price"]


def test_extra_metrics_populated_with_enriched_fields(db_session):
    asset = _asset(db_session, "V2METRICS")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    end = _insert_uptrend(db_session, asset, start)

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
    )
    assert result.num_trades > 0
    for key in ("gross_profit", "gross_loss", "sortino_ratio", "recovery_factor", "avg_exposure_pct", "turnover", "drawdown_detail", "streaks", "trade_distribution", "regime_breakdown", "total_fees"):
        assert key in result.extra_metrics
    assert result.extra_metrics["streaks"]["max_winning_streak"] >= 1
    assert result.data_fingerprint is not None
    assert len(result.equity_curve) > 0
    assert "exposure_pct" in result.equity_curve[0]
    assert "drawdown_pct" in result.equity_curve[0]


def test_data_integrity_blocks_backtest_on_bad_ohlc(db_session):
    asset = _asset(db_session, "V2BADOHLC")
    start = datetime.now(timezone.utc) - timedelta(minutes=50)
    for i in range(50):
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=100.0, high=90.0, low=95.0, close=100.0, volume=500.0, data_quality="high")
        )  # high < low: structurally impossible OHLC
    db_session.commit()

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=50), initial_capital=10_000.0,
    )
    assert result.notes["reason"] == "data_integrity_blocked"
    assert result.num_trades == 0
    assert any(i["code"] == "bad_ohlc_high_low" for i in result.notes["issues"])


def test_check_integrity_false_bypasses_the_gate(db_session):
    asset = _asset(db_session, "V2SKIPINTEGRITY")
    start = datetime.now(timezone.utc) - timedelta(minutes=50)
    for i in range(50):
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=100.0, high=90.0, low=95.0, close=100.0, volume=500.0, data_quality="high")
        )
    db_session.commit()

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=50), initial_capital=10_000.0, check_integrity=False,
    )
    assert result.notes.get("reason") != "data_integrity_blocked"


def test_lookahead_bias_no_future_price_changes_the_past(db_session):
    """Adversarial look-ahead test (§53): two candle series identical up to
    a cutoff, diverging sharply after it. If the engine ever peeked ahead,
    the two runs would differ before the cutoff; they must not."""
    asset_a = _asset(db_session, "V2LOOKA")
    asset_b = _asset(db_session, "V2LOOKB")
    start = datetime.now(timezone.utc) - timedelta(minutes=300)
    cutoff_bar = 250

    shared_closes = [100.0 * (1.004**i) for i in range(cutoff_bar)]
    # After the cutoff, A keeps rising; B crashes hard -- a look-ahead bug
    # would let this future divergence leak into pre-cutoff decisions.
    a_tail = [shared_closes[-1] * (1.004 ** (i + 1)) for i in range(50)]
    b_tail = [shared_closes[-1] * (0.95 ** (i + 1)) for i in range(50)]

    for asset, closes in ((asset_a, shared_closes + a_tail), (asset_b, shared_closes + b_tail)):
        for i, close in enumerate(closes):
            db_session.add(
                OHLCV(
                    asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999,
                    high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high",
                )
            )
    db_session.commit()

    cutoff_ts = start + timedelta(minutes=cutoff_bar)
    result_a = run_backtest(db_session, strategy=TrendFollowingStrategy(), asset_id=asset_a.id, symbol=asset_a.symbol, timeframe=TIMEFRAME, start_ts=start, end_ts=cutoff_ts, initial_capital=10_000.0)
    result_b = run_backtest(db_session, strategy=TrendFollowingStrategy(), asset_id=asset_b.id, symbol=asset_b.symbol, timeframe=TIMEFRAME, start_ts=start, end_ts=cutoff_ts, initial_capital=10_000.0)

    # Both runs only ever saw the identical shared prefix -- results up to
    # the cutoff must be identical regardless of what happens afterward.
    assert result_a.trades == result_b.trades
    assert result_a.net_return == result_b.net_return
    assert result_a.data_fingerprint == result_b.data_fingerprint


def test_news_aware_backtest_never_reads_news_created_after_the_bar(db_session):
    """Data leakage protection (§6, §34): a NewsImpact row created *after*
    a given bar's timestamp must never influence that bar's decision."""
    asset = _asset(db_session, "V2NEWSLEAK")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    end = _insert_uptrend(db_session, asset, start)

    # A NewsImpact row timestamped in the middle of the backtest window --
    # only bars from this point on should ever be able to see it.
    midpoint = start + timedelta(minutes=100)
    event = NewsEvent(headline="Some market news", source="test", category="earnings", published_at=midpoint)
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(news_event_id=event.id, asset_id=asset.id, impact="high", direction="bullish", confidence=0.9, horizon_hours=48.0, rationale="test", created_at=midpoint))
    db_session.commit()

    from packages.backtest.news_replay import news_signals_as_of

    before = news_signals_as_of(db_session, asset.id, midpoint - timedelta(minutes=1))
    after = news_signals_as_of(db_session, asset.id, midpoint + timedelta(minutes=1))
    assert before == []
    assert len(after) == 1

    # And the full backtest runs cleanly with news_aware=True even though
    # coverage is sparse -- an honest, expected outcome (see
    # packages/backtest/news_replay.py's module docstring), not a crash.
    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0, news_aware=True,
    )
    assert result.notes.get("reason") != "data_integrity_blocked"
