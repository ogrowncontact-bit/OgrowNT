""""PROMPT 7" §62 — the "complete simulation" acceptance test: one strategy
(BREAKOUT) across multiple assets and multiple timeframes, run through the
full pipeline the spec names — BACKTEST -> WALK FORWARD -> MONTE CARLO ->
STRESS TEST -> COST SENSITIVITY -> PARAMETER STABILITY -> OUT-OF-SAMPLE ->
"PAPER VALIDATION" (packages/backtest/reality_gap.py, since this system has
no live trading to validate against, only paper).

Honest limitation, stated once here rather than silently: §62 asks for
"multiple years when data available." This deployment's `ohlcv` table only
ever holds what the mock market data provider has actually produced
(packages/backtest/engine.py's own module docstring makes the same point) --
there is no multi-year historical dataset to run against. This test
synthesizes a few hundred bars per asset/timeframe instead (still real rows
in the real schema, just not years of history), and the assertions below
are scoped to what a short window can actually prove: every stage of the
pipeline runs end-to-end without error, on more than one asset and more
than one timeframe, and never once touches the paper trading tables.
"""
from datetime import datetime, timedelta, timezone

from packages.backtest.monte_carlo import run_monte_carlo
from packages.backtest.reality_gap import analyze_reality_gap
from packages.backtest.report import run_full_lab
from packages.backtest.sensitivity import run_cost_sensitivity
from packages.backtest.stability import check_parameter_stability
from packages.backtest.stress_test import SCENARIOS, run_stress_scenario
from packages.backtest.walkforward import run_walk_forward
from packages.quant.strategies import BreakoutStrategy
from packages.shared.models import OHLCV, Asset, Order, Position, StrategyRow, Trade

ASSETS = ("LABBTC", "LABETH", "LABEURUSD")
TIMEFRAMES = ("15m", "1h", "4h")
TIMEFRAME_MINUTES = {"15m": 15, "1h": 60, "4h": 240}
BARS = 250


def _seed_asset_timeframe(db_session, symbol: str, timeframe: str) -> tuple[Asset, datetime, datetime]:
    asset = db_session.query(Asset).filter(Asset.symbol == symbol).first()
    if asset is None:
        asset = Asset(symbol=symbol, asset_class="crypto" if "USD" not in symbol or symbol == "LABEURUSD" else "forex", is_active=True)
        db_session.add(asset)
        db_session.commit()

    minutes_per_bar = TIMEFRAME_MINUTES[timeframe]
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes_per_bar * BARS)
    # A mildly noisy uptrend, not a perfectly straight line -- gives the
    # breakout strategy real entries/exits to work with, and enough
    # variance for Monte Carlo/stability to have something to resample.
    for i in range(BARS):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        ts = start + timedelta(minutes=minutes_per_bar * i)
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=timeframe, ts=ts, open=close * 0.998, high=close * 1.006,
                low=close * 0.994, close=close, volume=500.0 + (i % 11) * 20, data_quality="high",
            )
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=minutes_per_bar * BARS)


def _strategy_row(db_session) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == "breakout_v1").first()
    if existing is not None:
        return existing
    row = StrategyRow(code="breakout_v1", name="Breakout", family="breakout", version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def test_complete_lab_pipeline_across_multiple_assets_and_timeframes(db_session):
    strategy_row = _strategy_row(db_session)
    results = []

    for symbol in ASSETS:
        for timeframe in TIMEFRAMES:
            asset, start, end = _seed_asset_timeframe(db_session, symbol, timeframe)

            # 1. BACKTEST
            report = run_full_lab(
                db_session, strategy_row=strategy_row, asset=asset, timeframe=timeframe, start_ts=start, end_ts=end,
                initial_capital=10_000.0, monte_carlo_simulations=100, run_stress_tests=False, run_walk_forward=False,
            )
            assert report["blocked"] is False, f"{symbol}/{timeframe}: {report.get('reason')}"
            results.append((symbol, timeframe, report))

            # 2. WALK FORWARD (a coarse consistency check across the window)
            wf = run_walk_forward(
                db_session, strategy=BreakoutStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
                start_ts=start, end_ts=end, window_days=(end - start).total_seconds() / 86400 / 3, initial_capital=10_000.0,
            )
            assert len(wf.windows) >= 1

            # 3. MONTE CARLO (over this window's own backtest trades)
            baseline_trades = report["performance"]["num_trades"]
            if baseline_trades > 0:
                from packages.backtest.engine import run_backtest

                raw = run_backtest(db_session, strategy=BreakoutStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe, start_ts=start, end_ts=end, initial_capital=10_000.0)
                mc = run_monte_carlo(raw.trades, initial_capital=10_000.0, method="bootstrap", num_simulations=100, random_seed=1)
                assert mc.num_simulations == 100

            # 4. STRESS TEST (spot-check one scenario per asset/timeframe to bound runtime)
            stress = run_stress_scenario(
                db_session, scenario="market_crash", strategy_factory=BreakoutStrategy, asset_id=asset.id, symbol=asset.symbol,
                timeframe=timeframe, start_ts=start, end_ts=end, initial_capital=10_000.0,
            )
            assert stress.scenario == "market_crash"

            # 5. COST SENSITIVITY
            cost = run_cost_sensitivity(
                db_session, strategy=BreakoutStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
                start_ts=start, end_ts=end, initial_capital=10_000.0,
            )
            assert len(cost.points) == 4

            # 6. PARAMETER STABILITY
            stability = check_parameter_stability(
                db_session, strategy_code="breakout_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
                start_ts=start, end_ts=end, initial_capital=10_000.0,
            )
            assert stability.base is not None

    assert len(results) == len(ASSETS) * len(TIMEFRAMES)
    # 7. OUT-OF-SAMPLE / "PAPER VALIDATION" -- no live trades exist for this
    # strategy in this test, so reality_gap honestly reports "no live
    # performance yet" rather than fabricating a comparison.
    gap = analyze_reality_gap(db_session, strategy_row.id)
    assert gap.notes  # always says something, never silently empty

    # Every stress scenario across the full SCENARIOS set at least once,
    # not just the crash spot-check above.
    asset, start, end = _seed_asset_timeframe(db_session, "LABBTC", "1h")
    for scenario in SCENARIOS:
        result = run_stress_scenario(
            db_session, scenario=scenario, strategy_factory=BreakoutStrategy, asset_id=asset.id, symbol=asset.symbol,
            timeframe="1h", start_ts=start, end_ts=end, initial_capital=10_000.0,
        )
        assert result.scenario == scenario


def test_no_live_trading_anywhere_in_the_lab_pipeline(db_session):
    """§66's own closing checklist item: "nenhum live trading foi
    implementado." Verified two ways: (a) packages/quant/news's existing
    structural guarantee extends to packages/backtest -- nothing in this
    phase imports packages.execution's order-submission path; (b) running
    the full lab pipeline never inserts a single row into `positions`,
    `orders`, or `trades` (the live/paper trading tables)."""
    import ast
    from pathlib import Path

    # Only import statements are checked, deliberately not every bare name
    # in the file: packages/backtest/engine.py's own event loop has a local
    # variable literally named `open_position` (the *simulated* position),
    # which would false-positive against a name-based scan. What actually
    # matters -- and is sufficient to prove nothing here can call the live
    # order manager -- is that the live functions are never imported at all.
    backtest_pkg = Path(__file__).resolve().parents[1] / "packages" / "backtest"
    for path in backtest_pkg.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "execution.adapters" not in node.module, f"{path.name} imports a live/paper execution adapter"
                assert "execution.order_manager" not in node.module, f"{path.name} imports the live order manager"

    strategy_row = _strategy_row(db_session)
    asset, start, end = _seed_asset_timeframe(db_session, "LABBTC", "1h")

    before_positions = db_session.query(Position).count()
    before_orders = db_session.query(Order).count()
    before_trades = db_session.query(Trade).count()

    run_full_lab(
        db_session, strategy_row=strategy_row, asset=asset, timeframe="1h", start_ts=start, end_ts=end,
        initial_capital=10_000.0, monte_carlo_simulations=50,
    )

    assert db_session.query(Position).count() == before_positions
    assert db_session.query(Order).count() == before_orders
    assert db_session.query(Trade).count() == before_trades
