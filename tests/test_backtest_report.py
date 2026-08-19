from datetime import datetime, timedelta, timezone

from packages.backtest.report import run_full_lab
from packages.shared.models import OHLCV, Asset, StrategyRow

TIMEFRAME = "1m"
REPORT_SECTIONS = (
    "configuration", "data", "strategy", "performance", "risk", "drawdown",
    "walk_forward", "monte_carlo", "stress_tests", "robustness", "parameter_stability",
    "reality_gap", "final_assessment",
)


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 200) -> None:
    for i in range(bars):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()


def test_full_lab_produces_all_thirteen_report_sections(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "LABREPORT")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_full_lab(
        db_session, strategy_row=strategy, asset=asset, timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200),
        initial_capital=10_000.0, monte_carlo_simulations=50,
    )
    assert report["blocked"] is False
    for section in REPORT_SECTIONS:
        assert section in report, f"missing report section: {section}"
    assert report["final_assessment"]["assessment"] in ("ROBUST", "PROMISING", "WEAK", "UNSTABLE", "INSUFFICIENT EVIDENCE")
    assert report["stress_tests"]  # every scenario ran


def test_full_lab_blocks_on_bad_data(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "LABREPORTBAD")
    start = datetime.now(timezone.utc) - timedelta(minutes=50)
    for i in range(50):
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=100.0, high=90.0, low=95.0, close=100.0, volume=500.0, data_quality="high")
        )
    db_session.commit()

    report = run_full_lab(db_session, strategy_row=strategy, asset=asset, timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=50), initial_capital=10_000.0)
    assert report["blocked"] is True
    assert report["reason"] == "BACKTEST_BLOCKED"


def test_full_lab_blocks_on_unregistered_strategy(db_session):
    strategy = StrategyRow(code="not_a_real_lab_strategy", name="x", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    asset = _asset(db_session, "LABREPORTUNREG")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_full_lab(db_session, strategy_row=strategy, asset=asset, timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0)
    assert report["blocked"] is True


def test_final_assessment_never_uses_forbidden_wording(db_session):
    strategy = _strategy(db_session, "breakout_v1")
    asset = _asset(db_session, "LABREPORTWORDING")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_full_lab(
        db_session, strategy_row=strategy, asset=asset, timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200),
        initial_capital=10_000.0, monte_carlo_simulations=50,
    )
    text_blob = str(report["final_assessment"]).lower()
    for phrase in ("guaranteed profit", "will make money"):
        assert phrase not in text_blob
